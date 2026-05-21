"""Two-step login flow against ``auth.gbm.com``.

The flow:

1. :func:`start_login` posts email + password and either returns a
   :class:`Session` (no 2FA) or raises :class:`MfaRequired` carrying the
   challenge state.
2. :func:`complete_mfa` takes the TOTP code plus the challenge state and
   posts to the challenge endpoint to obtain the actual tokens.
3. :func:`login` is the high-level helper that orchestrates both steps using
   a caller-supplied ``totp_provider`` callable for the TOTP code.

Endpoints discovered in Phase 0 (see ``docs/02-endpoints-discovered.md``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from gbm_mx_api.auth.session import Session
from gbm_mx_api.errors import ApiError, AuthError, MfaRequired
from gbm_mx_api.transport.http import HttpClient

# Public client id of the GBM web app. Not secret — visible in
# https://auth.gbm.com/signin?client_id=<this>.
DEFAULT_CLIENT_ID = "7c464570619a417080b300076e163289"

LOGIN_URL = "https://auth.gbm.com/api/v1/session/user"
CHALLENGE_URL = "https://auth.gbm.com/api/v1/session/user/challenge"

# CDMX downtown (Zócalo) — used when IP-based detection fails.
DEFAULT_LATITUDE = 19.4326
DEFAULT_LONGITUDE = -99.1332

TotpProvider = Callable[[], str]
"""Callable that returns a 6-digit TOTP code as a string."""


def detect_geo(timeout: float = 5.0) -> tuple[float, float]:
    """Look up an approximate (latitude, longitude) for the public IP.

    Uses the free ``ipapi.co`` service. On any failure (network, parsing,
    rate limit) falls back to CDMX coordinates. Never raises.
    """
    try:
        r = httpx.get("https://ipapi.co/json/", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return DEFAULT_LATITUDE, DEFAULT_LONGITUDE


def start_login(
    email: str,
    password: str,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Session:
    """Start the login flow.

    Returns a fully usable :class:`Session` if the account does NOT have 2FA
    enabled (rare). Raises :class:`MfaRequired` otherwise — the caller must
    pass the resulting challenge state to :func:`complete_mfa`.

    Raises:
        AuthError: on 401/403 (bad credentials).
        ApiError: on other 4xx/5xx.
        MfaRequired: when 2FA is required (the common case).
    """
    if latitude is None or longitude is None:
        lat, lon = detect_geo()
        latitude = latitude or lat
        longitude = longitude or lon

    try:
        with HttpClient(latitude=latitude, longitude=longitude) as http:
            body = http.post(
                LOGIN_URL,
                json={"clientid": client_id, "user": email, "password": password},
            )
    except ApiError as e:
        # GBM returns HTTP 422 NotAuthorizedException for bad credentials,
        # not the conventional 401. Reclassify so callers (and the
        # dashboard UI) can treat it as an auth failure rather than a
        # generic API error.
        if _looks_like_auth_failure(e):
            raise AuthError(
                _auth_error_message(e),
                status_code=e.status_code,
                body=e.body,
                request_id=e.request_id,
            ) from e
        raise

    if not isinstance(body, dict):
        raise ApiError(
            f"Unexpected login response shape: {type(body).__name__}",
            status_code=200,
            body=body,
        )

    # Path A: no MFA — token included directly.
    if "accessToken" in body:
        return _session_from_response(body, client_id, latitude, longitude)

    # Path B: MFA required — surface challenge state to caller.
    if body.get("id") == "ChallengeRequired":
        info = body.get("challengeInfo") or {}
        return _raise_mfa_required(info)

    raise ApiError("Login response did not contain token or challenge.", status_code=200, body=body)


def complete_mfa(
    challenge: MfaRequired,
    code: str,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Session:
    """Submit the TOTP ``code`` to complete a pending MFA challenge.

    Raises:
        AuthError: on 401/403 (wrong code, expired session).
        ApiError: on other failures.
    """
    if not (isinstance(code, str) and code.isdigit() and len(code) == 6):
        raise ValueError("TOTP code must be a 6-digit string.")

    if latitude is None or longitude is None:
        lat, lon = detect_geo()
        latitude = latitude or lat
        longitude = longitude or lon

    try:
        with HttpClient(latitude=latitude, longitude=longitude) as http:
            body = http.post(
                CHALLENGE_URL,
                json={
                    "clientid": client_id,
                    "user": challenge.user,
                    "session": challenge.session,
                    "code": code,
                    "challengeType": challenge.challenge_type,
                },
            )
    except ApiError as e:
        # GBM also returns 422 NotAuthorizedException when the TOTP code
        # is wrong or expired.
        if _looks_like_auth_failure(e):
            raise AuthError(
                _auth_error_message(e),
                status_code=e.status_code,
                body=e.body,
                request_id=e.request_id,
            ) from e
        raise

    if not isinstance(body, dict) or "accessToken" not in body:
        raise AuthError(
            "MFA response did not contain an access token.",
            status_code=200,
            body=body,
        )

    return _session_from_response(body, client_id, latitude, longitude)


def login(
    email: str,
    password: str,
    *,
    totp_provider: TotpProvider,
    client_id: str = DEFAULT_CLIENT_ID,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Session:
    """High-level: do the full login flow, asking ``totp_provider`` for the code.

    ``totp_provider`` is called only if the account has 2FA enabled. It must
    return a string of exactly 6 digits.

    Example:

        from gbm_mx_api.auth import login

        session = login(
            email="...",
            password="...",
            totp_provider=lambda: input("TOTP: ").strip(),
        )
        session.save()
    """
    if latitude is None or longitude is None:
        lat, lon = detect_geo()
        latitude = latitude or lat
        longitude = longitude or lon

    try:
        return start_login(
            email,
            password,
            client_id=client_id,
            latitude=latitude,
            longitude=longitude,
        )
    except MfaRequired as challenge:
        code = totp_provider()
        return complete_mfa(
            challenge,
            code,
            client_id=client_id,
            latitude=latitude,
            longitude=longitude,
        )


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------
# Known GBM error IDs that mean "credentials / TOTP rejected" — we treat
# these as AuthError so callers can react with a re-login UI instead of
# a generic API failure dialog.
_AUTH_FAILURE_IDS = frozenset({"NotAuthorizedException", "InvalidParameterException"})


def _looks_like_auth_failure(error: ApiError) -> bool:
    """True if an ApiError from auth.gbm.com is really an auth failure.

    GBM uses HTTP 422 with id=NotAuthorizedException for wrong
    credentials and wrong/expired TOTP codes — not the conventional 401.
    """
    if not isinstance(error.body, dict):
        return False
    return error.body.get("id") in _AUTH_FAILURE_IDS


def _auth_error_message(error: ApiError) -> str:
    """Best human-friendly message we can pull from a GBM auth error body."""
    if isinstance(error.body, dict):
        msg = error.body.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg
    return "Credentials rejected by GBM."


def _session_from_response(
    body: dict[str, Any],
    client_id: str,
    latitude: float,
    longitude: float,
) -> Session:
    return Session(
        access_token=body["accessToken"],
        identity_token=body.get("identityToken") or body.get("idToken"),
        refresh_token=body.get("refreshToken"),
        token_type=body.get("tokenType", "Bearer"),
        expires_in=int(body.get("expiresIn", 3600)),
        latitude=latitude,
        longitude=longitude,
        client_id=client_id,
    )


def _raise_mfa_required(info: dict[str, Any]) -> Session:
    """Always raises MfaRequired — return type is a lie for the caller's flow."""
    challenge_type = info.get("challengeType", "SOFTWARE_TOKEN_MFA")
    session = info.get("session")
    user = info.get("user")
    if not (isinstance(session, str) and isinstance(user, str)):
        raise ApiError(
            "Challenge response missing session/user fields.",
            status_code=200,
            body=info,
        )
    raise MfaRequired(challenge_type=challenge_type, session=session, user=user)
