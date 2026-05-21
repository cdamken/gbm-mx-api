"""Tests for the login flow against mocked auth.gbm.com."""

from __future__ import annotations

import httpx
import pytest
import respx

from gbm_mx_api.auth import complete_mfa, login, start_login
from gbm_mx_api.errors import AuthError, MfaRequired

LOGIN_URL = "https://auth.gbm.com/api/v1/session/user"
CHALLENGE_URL = "https://auth.gbm.com/api/v1/session/user/challenge"


@respx.mock
def test_start_login_raises_mfa_required_when_challenge() -> None:
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "ChallengeRequired",
                "code": 2,
                "challengeInfo": {
                    "challengeType": "SOFTWARE_TOKEN_MFA",
                    "session": "session-token-1",
                    "user": "user-uuid-1",
                    "timestamp": 1779120524467,
                },
            },
        )
    )
    with pytest.raises(MfaRequired) as ei:
        start_login(
            "carlos@example.com",
            "p4ssw0rd",
            latitude=19.4326,
            longitude=-99.1332,
        )
    assert ei.value.challenge_type == "SOFTWARE_TOKEN_MFA"
    assert ei.value.session == "session-token-1"
    assert ei.value.user == "user-uuid-1"


@respx.mock
def test_start_login_returns_session_when_no_mfa() -> None:
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "accessToken": "acc-1",
                "identityToken": "id-1",
                "refreshToken": "ref-1",
                "tokenType": "Bearer",
                "expiresIn": 3600,
            },
        )
    )
    session = start_login(
        "carlos@example.com",
        "p4ssw0rd",
        latitude=19.4326,
        longitude=-99.1332,
    )
    assert session.access_token == "acc-1"
    assert session.identity_token == "id-1"
    assert session.refresh_token == "ref-1"


@respx.mock
def test_start_login_401_raises_auth_error() -> None:
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(401, json={"message": "credenciales inválidas"})
    )
    with pytest.raises(AuthError):
        start_login(
            "carlos@example.com",
            "wrong",
            latitude=19.4326,
            longitude=-99.1332,
        )


@respx.mock
def test_start_login_422_not_authorized_raises_auth_error() -> None:
    """GBM returns 422 NotAuthorizedException for wrong credentials —
    we should classify it as an AuthError, not a generic ApiError."""
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            422,
            json={
                "code": 214,
                "id": "NotAuthorizedException",
                "message": "Verifica tu correo y contraseña.",
            },
        )
    )
    with pytest.raises(AuthError) as ei:
        start_login(
            "carlos@example.com",
            "wrong-password",
            latitude=19.4326,
            longitude=-99.1332,
        )
    assert "Verifica" in str(ei.value)
    assert ei.value.status_code == 422


@respx.mock
def test_complete_mfa_returns_session() -> None:
    respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "accessToken": "acc-2",
                "identityToken": "id-2",
                "refreshToken": "ref-2",
                "tokenType": "Bearer",
                "expiresIn": 3600,
            },
        )
    )
    challenge = MfaRequired(
        challenge_type="SOFTWARE_TOKEN_MFA",
        session="s",
        user="u",
    )
    session = complete_mfa(
        challenge,
        "123456",
        latitude=19.4326,
        longitude=-99.1332,
    )
    assert session.access_token == "acc-2"


def test_complete_mfa_rejects_bad_code() -> None:
    challenge = MfaRequired(
        challenge_type="SOFTWARE_TOKEN_MFA",
        session="s",
        user="u",
    )
    with pytest.raises(ValueError, match="6-digit"):
        complete_mfa(
            challenge,
            "abc123",
            latitude=19.4326,
            longitude=-99.1332,
        )
    with pytest.raises(ValueError, match="6-digit"):
        complete_mfa(
            challenge,
            "12345",
            latitude=19.4326,
            longitude=-99.1332,
        )


@respx.mock
def test_login_orchestrates_both_steps() -> None:
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "ChallengeRequired",
                "challengeInfo": {
                    "challengeType": "SOFTWARE_TOKEN_MFA",
                    "session": "s1",
                    "user": "u1",
                    "timestamp": 1,
                },
            },
        )
    )
    respx.post(CHALLENGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={"accessToken": "final", "tokenType": "Bearer", "expiresIn": 3600},
        )
    )
    session = login(
        "carlos@example.com",
        "p4ssw0rd",
        totp_provider=lambda: "654321",
        latitude=19.4326,
        longitude=-99.1332,
    )
    assert session.access_token == "final"
