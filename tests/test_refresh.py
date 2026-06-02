"""Tests for the silent Cognito refresh flow."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import respx

from gbm_mx_api.auth.refresh import COGNITO_URL, refresh_session
from gbm_mx_api.auth.session import Session
from gbm_mx_api.client import GbmClient
from gbm_mx_api.errors import AuthError, TransportError


def _session(**overrides: object) -> Session:
    defaults: dict[str, object] = {
        "access_token": "old-access",
        "identity_token": "old-identity",
        "refresh_token": "ref-token",
        "expires_in": 3600,
        "latitude": 19.4326,
        "longitude": -99.1332,
        "client_id": "test-client",
    }
    defaults.update(overrides)
    return Session(**defaults)  # type: ignore[arg-type]


@respx.mock
def test_refresh_session_success() -> None:
    respx.post(COGNITO_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "AuthenticationResult": {
                    "AccessToken": "new-access",
                    "IdToken": "new-identity",
                    "ExpiresIn": 3600,
                    "TokenType": "Bearer",
                },
                "ChallengeParameters": {},
            },
        )
    )
    s = _session(obtained_at=int(time.time()) - 4000)
    refreshed = refresh_session(s)

    assert refreshed.access_token == "new-access"
    assert refreshed.identity_token == "new-identity"
    # Refresh token must be preserved — Cognito does not return a new one.
    assert refreshed.refresh_token == "ref-token"
    assert refreshed.is_expired is False
    # Sanity: the original session object was not mutated.
    assert s.access_token == "old-access"


def test_refresh_session_without_refresh_token() -> None:
    s = _session(refresh_token=None)
    with pytest.raises(AuthError):
        refresh_session(s)


@respx.mock
def test_refresh_session_revoked_token() -> None:
    respx.post(COGNITO_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "__type": "NotAuthorizedException",
                "message": "Refresh Token has been revoked",
            },
        )
    )
    with pytest.raises(AuthError) as ei:
        refresh_session(_session())
    assert "revoked" in str(ei.value).lower()


@respx.mock
def test_refresh_session_network_error() -> None:
    respx.post(COGNITO_URL).mock(side_effect=httpx.ConnectError("no route"))
    with pytest.raises(TransportError):
        refresh_session(_session())


# ---------------------------------------------------------------------
# GbmClient.from_saved integration
# ---------------------------------------------------------------------
@respx.mock
def test_from_saved_refreshes_expired_session(tmp_path: Path) -> None:
    """Expired session + valid refresh_token → silent refresh, no TOTP."""
    path = tmp_path / "session.json"
    _session(obtained_at=int(time.time()) - 4000).save(path)

    respx.post(COGNITO_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "AuthenticationResult": {
                    "AccessToken": "new-access",
                    "IdToken": "new-identity",
                    "ExpiresIn": 3600,
                    "TokenType": "Bearer",
                },
                "ChallengeParameters": {},
            },
        )
    )

    client = GbmClient.from_saved(path)
    assert client is not None
    assert client.session.access_token == "new-access"

    # Refreshed session must be persisted so subsequent runs don't refresh again.
    reloaded = Session.load(path)
    assert reloaded.access_token == "new-access"
    assert reloaded.refresh_token == "ref-token"


@respx.mock
def test_from_saved_returns_none_when_refresh_fails(tmp_path: Path) -> None:
    """Expired session + refresh rejected by Cognito → None (caller does TOTP)."""
    path = tmp_path / "session.json"
    _session(obtained_at=int(time.time()) - 4000).save(path)

    respx.post(COGNITO_URL).mock(
        return_value=httpx.Response(
            400,
            json={"__type": "NotAuthorizedException", "message": "revoked"},
        )
    )

    assert GbmClient.from_saved(path) is None


def test_from_saved_returns_none_when_expired_without_refresh_token(
    tmp_path: Path,
) -> None:
    path = tmp_path / "session.json"
    _session(obtained_at=int(time.time()) - 4000, refresh_token=None).save(path)

    assert GbmClient.from_saved(path) is None
