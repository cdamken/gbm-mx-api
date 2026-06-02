"""Silent session refresh via Cognito ``REFRESH_TOKEN_AUTH``.

GBM's login flow goes through ``auth.gbm.com`` (which wraps Cognito), but
the refresh flow is plain Cognito ``InitiateAuth`` against
``cognito-idp.us-east-1.amazonaws.com``. The Cognito app client used by
GBM is public (no client secret), so the call is just:

    POST https://cognito-idp.us-east-1.amazonaws.com/
    X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth
    Content-Type: application/x-amz-json-1.1
    {
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": "<COGNITO_CLIENT_ID>",
        "AuthParameters": {"REFRESH_TOKEN": "<refresh_token>"}
    }

The response gives back fresh ``AccessToken`` and ``IdToken`` (both 1 h)
but NO new ``RefreshToken`` — the original keeps working until Cognito
invalidates it (typically 30 days, configurable per user pool).

This module is intentionally decoupled from the GBM ``HttpClient`` (no
geo headers, no Bearer): Cognito doesn't need them, and calling Cognito
directly means a refresh works even if ``auth.gbm.com`` is temporarily
down.
"""

from __future__ import annotations

import contextlib
import logging
import time

import httpx

from gbm_mx_api.auth.session import Session
from gbm_mx_api.errors import AuthError, TransportError

log = logging.getLogger(__name__)

# Public Cognito app client used by GBM+ (extracted from the JWT's
# ``client_id`` claim). Not a secret — anyone with a GBM session can read
# it from their own access token. The GBM client_id stored in the session
# (e.g. ``7c464570619a417080b300076e163289``) is a DIFFERENT value used
# by ``auth.gbm.com``; that one is not accepted by Cognito directly.
COGNITO_CLIENT_ID = "6eptudi9rs762jtc50ktjb16nl"
COGNITO_URL = "https://cognito-idp.us-east-1.amazonaws.com/"
COGNITO_TARGET = "AWSCognitoIdentityProviderService.InitiateAuth"

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def refresh_session(session: Session, *, timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> Session:
    """Use ``session.refresh_token`` to mint a new access/id token pair.

    Returns a new :class:`Session` with the same ``refresh_token`` and
    a fresh ``access_token`` / ``identity_token`` / ``obtained_at``.
    The original :class:`Session` is left untouched (sessions are
    Pydantic models, semantically immutable).

    Raises:
        AuthError: when the refresh token is missing, expired, or
            revoked. The caller should fall back to a full login
            (i.e. ask the user for the TOTP code).
        TransportError: on network failure talking to Cognito.
    """
    if not session.refresh_token:
        raise AuthError(
            "No refresh token in session; cannot refresh silently.",
            status_code=0,
        )

    try:
        response = httpx.post(
            COGNITO_URL,
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": COGNITO_TARGET,
            },
            json={
                "AuthFlow": "REFRESH_TOKEN_AUTH",
                "ClientId": COGNITO_CLIENT_ID,
                "AuthParameters": {"REFRESH_TOKEN": session.refresh_token},
            },
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise TransportError(f"POST {COGNITO_URL}: {exc}") from exc

    if response.status_code != 200:
        # Cognito returns 400 with __type="NotAuthorizedException" when
        # the refresh token has been revoked or has expired. Surface
        # that as AuthError so the dashboard knows to fall back to TOTP.
        body: object = response.text
        with contextlib.suppress(ValueError):
            body = response.json()
        type_ = body.get("__type") if isinstance(body, dict) else None
        msg = (
            body.get("message") or body.get("Message") if isinstance(body, dict) else None
        ) or f"Cognito refresh failed: HTTP {response.status_code}"
        log.info("refresh_session failed: %s (%s)", type_ or "?", msg)
        raise AuthError(msg, status_code=response.status_code, body=body)

    data = response.json()
    auth = data.get("AuthenticationResult") or {}
    new_access = auth.get("AccessToken")
    if not new_access:
        raise AuthError(
            "Cognito refresh response missing AccessToken.",
            status_code=200,
            body=data,
        )

    # Cognito does NOT return a new RefreshToken on REFRESH_TOKEN_AUTH —
    # the original keeps working until invalidated. So we carry it over.
    return session.model_copy(
        update={
            "access_token": new_access,
            "identity_token": auth.get("IdToken") or session.identity_token,
            "token_type": auth.get("TokenType") or session.token_type,
            "expires_in": int(auth.get("ExpiresIn", session.expires_in)),
            "obtained_at": int(time.time()),
        }
    )
