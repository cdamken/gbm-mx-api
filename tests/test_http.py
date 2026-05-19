"""Tests for the HttpClient using respx to mock the backend."""

from __future__ import annotations

import httpx
import pytest
import respx

from gbm_mx_api.errors import ApiError, AuthError, RateLimited, TransportError
from gbm_mx_api.transport.http import HttpClient


@pytest.fixture
def client(fixed_geo: tuple[float, float]) -> HttpClient:
    lat, lon = fixed_geo
    return HttpClient(latitude=lat, longitude=lon, access_token="tok-1")


@respx.mock
def test_get_returns_parsed_json(client: HttpClient) -> None:
    route = respx.get("https://api.example.com/x").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    out = client.get("https://api.example.com/x")
    assert out == {"ok": True}
    assert route.called


@respx.mock
def test_sends_geo_and_bearer_headers(client: HttpClient) -> None:
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={})

    respx.get("https://api.example.com/x").mock(side_effect=_capture)
    client.get("https://api.example.com/x")

    h = captured["headers"]
    assert h["device-latitude"] == "19.4326"
    assert h["device-longitude"] == "-99.1332"
    assert h["authorization"] == "Bearer tok-1"


@respx.mock
def test_401_raises_auth_error(client: HttpClient) -> None:
    respx.get("https://api.example.com/x").mock(
        return_value=httpx.Response(401, json={"message": "bad token"})
    )
    with pytest.raises(AuthError) as ei:
        client.get("https://api.example.com/x")
    assert ei.value.status_code == 401


@respx.mock
def test_500_retries_then_raises(client: HttpClient) -> None:
    # Three 500s — client retries up to max_retries=2 then raises.
    respx.get("https://api.example.com/x").mock(return_value=httpx.Response(500, json={}))
    with pytest.raises(ApiError):
        client.get("https://api.example.com/x")


@respx.mock
def test_429_raises_rate_limited_with_retry_after(client: HttpClient) -> None:
    respx.get("https://api.example.com/x").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"}, json={})
    )
    with pytest.raises(RateLimited) as ei:
        client.get("https://api.example.com/x")
    assert ei.value.retry_after == 30.0


@respx.mock
def test_network_error_wrapped_as_transport(client: HttpClient) -> None:
    respx.get("https://api.example.com/x").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(TransportError):
        client.get("https://api.example.com/x")


def test_set_access_token_updates_header(fixed_geo: tuple[float, float]) -> None:
    lat, lon = fixed_geo
    with HttpClient(latitude=lat, longitude=lon) as client:
        client.set_access_token("new-tok")
        # We can't easily peek headers without a real call; check internal state
        # via making a mocked request.
        with respx.mock:
            captured = {}

            def _capture(request: httpx.Request) -> httpx.Response:
                captured["auth"] = request.headers.get("authorization")
                return httpx.Response(200, json={})

            respx.get("https://api.example.com/x").mock(side_effect=_capture)
            client.get("https://api.example.com/x")
            assert captured["auth"] == "Bearer new-tok"
