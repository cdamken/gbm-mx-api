"""Integration-style tests for the API modules against mocked HTTP."""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal

import httpx
import pytest
import respx

from gbm_mx_api.api.accounts import Accounts
from gbm_mx_api.api.contracts import Contracts
from gbm_mx_api.api.orders import Orders
from gbm_mx_api.api.positions import Positions
from gbm_mx_api.errors import ApiError
from gbm_mx_api.transport.http import HttpClient
from tests.fixtures import (
    ACCOUNTS_RESPONSE,
    BLOTTER_TWO_ORDERS,
    CONTRACTS_RESPONSE,
    POSITION_SUMMARY_RESPONSE,
    blotter_response,
)

CONTRACT_ID = "00000000-0000-4000-8000-000000000001"
LEGACY_ID = "AB12CD05"


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(latitude=19.4326, longitude=-99.1332, access_token="tok-1")


# ----------------------------------------------------------------------
# Contracts
# ----------------------------------------------------------------------
@respx.mock
def test_contracts_list(http: HttpClient) -> None:
    respx.get("https://api.gbm.com/v1/contracts").mock(
        return_value=httpx.Response(200, json=CONTRACTS_RESPONSE)
    )
    api = Contracts(http)
    out = api.list()
    assert len(out) == 1
    assert out[0].legacy_contract_id == "AB12CD"


@respx.mock
def test_contracts_get_main(http: HttpClient) -> None:
    respx.get("https://api.gbm.com/v1/contracts").mock(
        return_value=httpx.Response(200, json=CONTRACTS_RESPONSE)
    )
    api = Contracts(http)
    main = api.get_main()
    assert main.contract_id == CONTRACT_ID


@respx.mock
def test_contracts_get_main_empty_raises(http: HttpClient) -> None:
    respx.get("https://api.gbm.com/v1/contracts").mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(ApiError, match="No contracts"):
        Contracts(http).get_main()


# ----------------------------------------------------------------------
# Accounts
# ----------------------------------------------------------------------
@respx.mock
def test_accounts_list(http: HttpClient) -> None:
    respx.get(f"https://api.gbm.com/v2/contracts/{CONTRACT_ID}/accounts").mock(
        return_value=httpx.Response(200, json=ACCOUNTS_RESPONSE)
    )
    out = Accounts(http).list(CONTRACT_ID)
    assert {a.management_type_template for a in out} == {"trading", "trading_usa"}


@respx.mock
def test_accounts_get_trading(http: HttpClient) -> None:
    respx.get(f"https://api.gbm.com/v2/contracts/{CONTRACT_ID}/accounts").mock(
        return_value=httpx.Response(200, json=ACCOUNTS_RESPONSE)
    )
    trading = Accounts(http).get_trading(CONTRACT_ID)
    assert trading.legacy_contract_id == "AB12CD05"


@respx.mock
def test_accounts_get_trading_missing_raises(http: HttpClient) -> None:
    respx.get(f"https://api.gbm.com/v2/contracts/{CONTRACT_ID}/accounts").mock(
        return_value=httpx.Response(200, json=[ACCOUNTS_RESPONSE[1]])  # only USA
    )
    with pytest.raises(ApiError, match="trading"):
        Accounts(http).get_trading(CONTRACT_ID)


# ----------------------------------------------------------------------
# Positions
# ----------------------------------------------------------------------
@respx.mock
def test_positions_summary(http: HttpClient) -> None:
    respx.post("https://homebroker-api.gbm.com/GBMP/api/Portfolio/GetPositionSummary").mock(
        return_value=httpx.Response(200, json=POSITION_SUMMARY_RESPONSE)
    )
    s = Positions(http).summary(LEGACY_ID)
    assert s.total_market_value == Decimal("151405.11")
    assert len(s.real_positions) == 2


# ----------------------------------------------------------------------
# Orders
# ----------------------------------------------------------------------
@respx.mock
def test_orders_list_for_day(http: HttpClient) -> None:
    respx.post("https://homebroker-api.gbm.com/GBMP/api/Operation/GetBlotterOrders").mock(
        return_value=httpx.Response(200, json=BLOTTER_TWO_ORDERS)
    )
    out = Orders(http).list_for_day(LEGACY_ID, _dt.date(2026, 5, 14))
    assert len(out) == 2
    assert {o.sob_id for o in out} == {109142599, 109116247}


@respx.mock
def test_orders_list_for_day_sends_correct_payload(http: HttpClient) -> None:
    captured: dict[str, object] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content.decode())
        return httpx.Response(200, json=BLOTTER_TWO_ORDERS)

    respx.post("https://homebroker-api.gbm.com/GBMP/api/Operation/GetBlotterOrders").mock(
        side_effect=_capture
    )
    Orders(http).list_for_day(LEGACY_ID, _dt.date(2026, 5, 14))

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["contractId"] == LEGACY_ID
    assert body["instrumentTypes"] == [0, 2]
    assert body["processDate"] == "2026-05-14T06:00:00Z"


@respx.mock
def test_orders_list_filled_filters_and_sorts(http: HttpClient) -> None:
    # Day 14 has one filled + one cancelled (from fixture).
    # Day 15 has another filled to verify ordering.
    day15_response = blotter_response(
        [
            {
                **BLOTTER_TWO_ORDERS["ordersList"][0],
                "sobId": 109200000,
                "issueId": "FMTY 14",
                "averagePrice": 14.66,
                "price": 14.66,
                "commision": 0.03,
                "processDate": "2026-05-15T08:25:46.00-06:00",
            }
        ]
    )
    respx.post("https://homebroker-api.gbm.com/GBMP/api/Operation/GetBlotterOrders").mock(
        side_effect=[
            httpx.Response(200, json=BLOTTER_TWO_ORDERS),  # day 14
            httpx.Response(200, json=day15_response),  # day 15
        ]
    )
    out = Orders(http).list_filled(LEGACY_ID, _dt.date(2026, 5, 14), _dt.date(2026, 5, 15))
    assert [o.sob_id for o in out] == [109142599, 109200000]  # chronological
    # cancelled order excluded
    assert all(o.issue_id != "GAP B" for o in out)


@respx.mock
def test_orders_list_filled_dedupes_by_sob_id(http: HttpClient) -> None:
    """Defensive: if the backend returns the same order on two consecutive
    days, we should not double-count."""
    respx.post("https://homebroker-api.gbm.com/GBMP/api/Operation/GetBlotterOrders").mock(
        side_effect=[
            httpx.Response(200, json=BLOTTER_TWO_ORDERS),
            httpx.Response(200, json=BLOTTER_TWO_ORDERS),  # same again
        ]
    )
    out = Orders(http).list_filled(LEGACY_ID, _dt.date(2026, 5, 14), _dt.date(2026, 5, 15))
    assert len(out) == 1


def test_orders_list_filled_rejects_inverted_range(http: HttpClient) -> None:
    with pytest.raises(ValueError, match="from_date"):
        Orders(http).list_filled(LEGACY_ID, _dt.date(2026, 5, 15), _dt.date(2026, 5, 14))
