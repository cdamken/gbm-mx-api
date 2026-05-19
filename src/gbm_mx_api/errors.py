"""Exception hierarchy.

All exceptions raised by this package descend from :class:`GbmError`, so
callers can catch them broadly when desired.
"""

from __future__ import annotations

from typing import Any


class GbmError(Exception):
    """Base class for all errors raised by gbm-mx-api."""


class TransportError(GbmError):
    """Network / HTTP layer failure (DNS, connection, timeout, TLS, etc.).

    Wraps the underlying ``httpx`` exception in ``__cause__``.
    """


class ApiError(GbmError):
    """The backend returned an HTTP error response.

    Attributes:
        status_code: HTTP status code returned.
        body: Parsed JSON body if available, else the raw text.
        request_id: Optional X-Amzn-RequestId for support tickets.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.request_id = request_id

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        base = super().__str__()
        return f"{base} (HTTP {self.status_code})"


class AuthError(ApiError):
    """Authentication failed (wrong credentials, expired token, etc.)."""


class MfaRequired(GbmError):
    """The login flow requires a second factor that the caller must supply.

    Raised from :func:`gbm_mx_api.auth.login.start_login` when GBM returns the
    ``ChallengeRequired`` response. The caller is expected to obtain the TOTP
    code from the user and call :func:`complete_mfa_challenge` with the
    challenge state preserved on this instance.

    Attributes:
        challenge_type: e.g. ``"SOFTWARE_TOKEN_MFA"``.
        session: Opaque session token that must be echoed back to the backend.
        user: Cognito user id that must be echoed back.
    """

    def __init__(self, challenge_type: str, session: str, user: str) -> None:
        super().__init__(f"MFA challenge required: {challenge_type}")
        self.challenge_type = challenge_type
        self.session = session
        self.user = user


class RateLimited(ApiError):
    """HTTP 429 from the backend.

    Attributes:
        retry_after: Optional seconds to wait, parsed from ``Retry-After``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        body: Any = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body, request_id=request_id)
        self.retry_after = retry_after
