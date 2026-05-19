"""Tests for the GbmClient facade."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import respx

from gbm_mx_api import GbmClient, Session
from gbm_mx_api.errors import GbmError
from tests.fixtures import CONTRACTS_RESPONSE


def _fresh_session() -> Session:
    return Session(
        access_token="tok-1",
        expires_in=3600,
        obtained_at=int(time.time()),
        latitude=19.4326,
        longitude=-99.1332,
        client_id="test-client",
    )


def _expired_session() -> Session:
    return Session(
        access_token="tok-1",
        expires_in=10,
        obtained_at=int(time.time()) - 100,
        latitude=19.4326,
        longitude=-99.1332,
        client_id="test-client",
    )


def test_from_session_rejects_expired() -> None:
    with pytest.raises(GbmError, match="expired"):
        GbmClient.from_session(_expired_session())


def test_from_session_returns_usable_client() -> None:
    client = GbmClient.from_session(_fresh_session())
    assert hasattr(client, "contracts")
    assert hasattr(client, "accounts")
    assert hasattr(client, "positions")
    assert hasattr(client, "orders")


@respx.mock
def test_client_routes_calls_with_bearer_token() -> None:
    respx.get("https://api.gbm.com/v1/contracts").mock(
        return_value=httpx.Response(200, json=CONTRACTS_RESPONSE)
    )
    with GbmClient.from_session(_fresh_session()) as client:
        contracts = client.contracts.list()
    assert contracts[0].legacy_contract_id == "AB12CD"


def test_from_saved_returns_none_when_missing(tmp_path: Path) -> None:
    assert GbmClient.from_saved(tmp_path / "nope.json") is None


def test_from_saved_returns_none_when_expired(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    _expired_session().save(path)
    assert GbmClient.from_saved(path) is None


def test_from_saved_returns_client_when_fresh(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    _fresh_session().save(path)
    client = GbmClient.from_saved(path)
    assert client is not None
    assert client.session.access_token == "tok-1"
    client.close()
