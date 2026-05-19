"""HTTP client used by every API module.

Single point of HTTP I/O. Keeps a long-lived ``httpx.Client`` and injects
common GBM requirements (auth, geo, redacted logging).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

import httpx

from gbm_mx_api.errors import ApiError, AuthError, RateLimited, TransportError
from gbm_mx_api.transport.redaction import redact

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
DEFAULT_USER_AGENT = "gbm-mx-api/0.1 (+https://github.com/cdamken/gbm-mx-api)"


class HttpClient:
    """Thin wrapper around ``httpx.Client`` with GBM-specific defaults.

    Args:
        latitude: ``device-latitude`` header value (anti-fraud).
        longitude: ``device-longitude`` header value (anti-fraud).
        access_token: Optional Bearer token; if set, sent as
            ``Authorization: Bearer <token>``.
        user_agent: HTTP User-Agent header.
        timeout: ``httpx.Timeout`` for all calls.
        max_retries: Number of retries on 5xx responses for idempotent verbs.
    """

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        access_token: str | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._access_token = access_token
        self._max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "device-latitude": str(latitude),
                "device-longitude": str(longitude),
            },
            follow_redirects=False,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_access_token(self, token: str | None) -> None:
        """Update or clear the Bearer token used for subsequent calls."""
        self._access_token = token

    def get(self, url: str, *, params: Mapping[str, Any] | None = None) -> Any:
        return self._request("GET", url, params=params)

    def post(self, url: str, *, json: Any = None) -> Any:
        return self._request("POST", url, json=json)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        headers = self._auth_headers()
        log.debug(
            "→ %s %s params=%s json=%s",
            method,
            url,
            redact(dict(params or {})),
            redact(json),
        )

        attempt = 0
        last_exc: Exception | None = None
        while True:
            try:
                response = self._client.request(
                    method, url, headers=headers, params=params, json=json
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self._max_retries and method in ("GET", "HEAD"):
                    attempt += 1
                    time.sleep(min(2**attempt, 5))
                    continue
                raise TransportError(f"{method} {url}: {exc}") from exc

            log.debug("← HTTP %s %s", response.status_code, response.reason_phrase)

            # 2xx — happy path
            if response.is_success:
                return _parse_body(response)

            # 429 — rate limited
            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                raise RateLimited(
                    f"{method} {url}: rate limited",
                    body=_safe_body(response),
                    request_id=response.headers.get("x-amzn-RequestId"),
                    retry_after=retry_after,
                )

            # 401/403 — auth specifically
            if response.status_code in (401, 403):
                raise AuthError(
                    f"{method} {url}: authentication failed",
                    status_code=response.status_code,
                    body=_safe_body(response),
                    request_id=response.headers.get("x-amzn-RequestId"),
                )

            # 5xx — retry idempotent
            if (
                500 <= response.status_code < 600
                and method in ("GET", "HEAD")
                and attempt < self._max_retries
            ):
                attempt += 1
                time.sleep(min(2**attempt, 5))
                continue

            # Anything else — generic API error
            raise ApiError(
                f"{method} {url}: {response.status_code} {response.reason_phrase}",
                status_code=response.status_code,
                body=_safe_body(response),
                request_id=response.headers.get("x-amzn-RequestId"),
            )

        # Defensive (unreachable): ensure typed return.
        raise TransportError(f"{method} {url}: unreachable") from last_exc


def _parse_body(response: httpx.Response) -> Any:
    """Return parsed JSON if possible, else raw text. None on 204."""
    if response.status_code == 204 or not response.content:
        return None
    ctype = response.headers.get("content-type", "")
    if "application/json" in ctype:
        return response.json()
    return response.text


def _safe_body(response: httpx.Response) -> Any:
    try:
        return _parse_body(response)
    except Exception:
        return response.text[:500]


def _parse_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
