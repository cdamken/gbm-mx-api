"""Silent session refresh via auth.gbm.com.

The refresh goes through GBM's own gateway, NOT Cognito directly:

    POST https://auth.gbm.com/api/v1/session/user/refresh
    Content-Type: application/json
    device-latitude / device-longitude   (anti-fraud, required)
    {"ClientId": "<client_id>", "RefreshToken": "<refresh_token>"}

→ {"accessToken", "idToken", "refreshToken"?, "expiresIn", "tokenType"}

Why not Cognito? GBM ties api.gbm.com authorization to a session that
auth.gbm.com establishes at login. A raw Cognito ``REFRESH_TOKEN_AUTH`` DOES
mint a syntactically-valid access token, but api.gbm.com 401s it because no
GBM session backs it — which manifested as a re-TOTP loop even though the
refresh "succeeded". Refreshing through auth.gbm.com yields the same kind of
token login does, which api.gbm.com accepts. (Discovered 2026-06-20 by
endpoint probing; the established 2021-era gbmplus libs never refreshed — they
just re-logged in with email+password, which only worked pre-2FA.)

``global_signout`` below still talks to Cognito (GlobalSignOut) — that part of
the Cognito surface still works for revoking the refresh token server-side.
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
COGNITO_SIGNOUT_TARGET = "AWSCognitoIdentityProviderService.GlobalSignOut"

# auth.gbm.com's own refresh endpoint. This is what the GBM web app uses and
# is the ONLY refresh that yields a token api.gbm.com accepts. A raw Cognito
# REFRESH_TOKEN_AUTH *does* mint a syntactically-valid access token, but
# api.gbm.com 401s it — GBM ties API authorization to a session established by
# auth.gbm.com at login, which a direct-to-Cognito refresh never recreates.
# Discovered 2026-06-20 by probing the endpoint (it requires exactly the
# PascalCase fields ClientId + RefreshToken). See ADR / memory.
GBM_REFRESH_URL = "https://auth.gbm.com/api/v1/session/user/refresh"

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def refresh_session(session: Session, *, timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> Session:
    """Use ``session.refresh_token`` to mint a fresh access/id token pair.

    Refreshes through **auth.gbm.com** (not Cognito directly): GBM only honors
    API calls whose Bearer token was issued by the auth.gbm.com login session,
    so the refresh has to go through the same gateway. Returns a new
    :class:`Session` with a fresh ``access_token`` / ``identity_token`` /
    ``obtained_at`` (and the rotated ``refresh_token`` if the server sends one).
    The original :class:`Session` is left untouched.

    Raises:
        AuthError: when the refresh token is missing, expired, or revoked
            (the caller should fall back to a full login, i.e. ask for TOTP).
        TransportError: on network failure talking to auth.gbm.com.
    """
    if not session.refresh_token:
        raise AuthError(
            "No refresh token in session; cannot refresh silently.",
            status_code=0,
        )
    if not session.client_id:
        raise AuthError("No client_id in session; cannot refresh.", status_code=0)

    # device-latitude/longitude are anti-fraud headers auth.gbm.com requires on
    # every call (same as login); without them it 400s before auth.
    headers = {
        "Content-Type": "application/json",
        "device-latitude": str(session.latitude),
        "device-longitude": str(session.longitude),
    }
    try:
        response = httpx.post(
            GBM_REFRESH_URL,
            headers=headers,
            json={"ClientId": session.client_id, "RefreshToken": session.refresh_token},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise TransportError(f"POST {GBM_REFRESH_URL}: {exc}") from exc

    if response.status_code != 200:
        # 401 = refresh token revoked/expired; 400 = malformed. Either way the
        # caller must fall back to a fresh TOTP login.
        body: object = response.text
        with contextlib.suppress(ValueError):
            body = response.json()
        msg = (
            (body.get("message") or body.get("title")) if isinstance(body, dict) else None
        ) or f"GBM refresh failed: HTTP {response.status_code}"
        log.info("refresh_session failed: HTTP %s (%s)", response.status_code, msg)
        raise AuthError(msg, status_code=response.status_code, body=body)

    data = response.json()
    new_access = data.get("accessToken")
    if not new_access:
        raise AuthError(
            "GBM refresh response missing accessToken.",
            status_code=200,
            body=data,
        )

    return session.model_copy(
        update={
            "access_token": new_access,
            "identity_token": data.get("identityToken")
            or data.get("idToken")
            or session.identity_token,
            # auth.gbm.com may rotate the refresh token; keep the old one if not.
            "refresh_token": data.get("refreshToken") or session.refresh_token,
            "token_type": data.get("tokenType") or session.token_type,
            "expires_in": int(data.get("expiresIn", session.expires_in)),
            "obtained_at": int(time.time()),
        }
    )


def global_signout(session: Session, *, timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> None:
    """Revoke the session server-side via Cognito GlobalSignOut.

    Invalidates the access token AND the refresh token for this user
    across every device. Useful for a true "log out everywhere" — e.g.
    the user's laptop was stolen and they want to make sure the cached
    refresh token can never mint another access token.

    After this returns, the local session.json is effectively dead and
    should be deleted by the caller; any further API call will get a
    401 from GBM and the user must re-login from scratch (full TOTP).

    Raises:
        AuthError: when Cognito rejects the signout (most commonly,
            the access token is already expired — in which case the
            session is already partly dead anyway).
        TransportError: on network failure talking to Cognito.

    Note: requires a *valid* (non-expired) access token. If your stored
    session is expired, call refresh_session() first to mint a fresh
    one, then call global_signout(). Otherwise Cognito returns
    NotAuthorizedException ("Access Token has expired").
    """
    if not session.access_token:
        raise AuthError("No access token in session; cannot sign out.", status_code=0)

    try:
        response = httpx.post(
            COGNITO_URL,
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": COGNITO_SIGNOUT_TARGET,
            },
            json={"AccessToken": session.access_token},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise TransportError(f"POST {COGNITO_URL} GlobalSignOut: {exc}") from exc

    if response.status_code != 200:
        body: object = response.text
        with contextlib.suppress(ValueError):
            body = response.json()
        type_ = body.get("__type") if isinstance(body, dict) else None
        msg = (
            body.get("message") or body.get("Message") if isinstance(body, dict) else None
        ) or f"Cognito GlobalSignOut failed: HTTP {response.status_code}"
        log.info("global_signout failed: %s (%s)", type_ or "?", msg)
        raise AuthError(msg, status_code=response.status_code, body=body)
    # Success: response body is `{}` per Cognito spec — nothing to return.
