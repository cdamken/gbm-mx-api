"""Integration-style tests for the API modules against mocked HTTP."""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal

import httpx
import pytest
import respx

from gbm_mx_api.api.accounts import Accounts
from gbm_mx_api.api.contracts import Contracts
from gbm_mx_api.api.dividends import Dividends
from gbm_mx_api.api.orders import Orders
from gbm_mx_api.api.positions import Positions
from gbm_mx_api.api.transactions import Transactions
from gbm_mx_api.domain.transaction import Transaction
from gbm_mx_api.errors import ApiError
from gbm_mx_api.transport.http import HttpClient
from tests.fixtures import (
    ACCOUNTS_RESPONSE,
    BLOTTER_TWO_ORDERS,
    CONTRACTS_RESPONSE,
    DIVIDENDS_THREE_ITEMS,
    POSITION_SUMMARY_RESPONSE,
    TRANSACTIONS_MIXED,
    blotter_response,
    dividends_page,
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


@respx.mock
def test_positions_summary_sends_account_id_when_provided(http: HttpClient) -> None:
    """Asesor + Trading USA require accountId; the primary trading account
    works without. Ensure the body shape varies accordingly."""
    captured: dict[str, object] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content.decode())
        return httpx.Response(200, json=POSITION_SUMMARY_RESPONSE)

    respx.post("https://homebroker-api.gbm.com/GBMP/api/Portfolio/GetPositionSummary").mock(
        side_effect=_capture
    )

    Positions(http).summary(LEGACY_ID, account_id="acct-uuid-1")

    body = captured["body"]
    assert isinstance(body, dict)
    assert body == {"request": LEGACY_ID, "accountId": "acct-uuid-1"}


@respx.mock
def test_positions_summary_parses_new_sections(http: HttpClient) -> None:
    """The model accepts mercado_extranjero (USA) and sociedades_inversion_comun
    (Asesor) sections discovered in v0.1.1."""
    extended_response = {
        "mercadosGlobalesSIC": [],
        "mercadoCapitales": [],
        "sociedadesInversionDeuda": [],
        "sociedadesInversionComun": [
            {
                "positionValueType": 2,
                "issueId": "GBMAAA BO",
                "issueName": "GBM INSTRUMENTOS BURSATILES",
                "instrumentType": 28,
                "quantity": 10325.0,
                "averagePrice": 1.934,
                "lastPrice": 2.069,
                "closePrice": 2.069,
                "weightedAveragePrice": 0.0,
                "yieldValue": 1401.0,
                "marketValue": 21364.0,
                "dailyVariationPercentage": 0.0,
                "historicalVariationPercentage": 0.07,
                "averageCost": 19963.0,
                "positionPercentage": 0.2,
            }
        ],
        "mercadoExtranjero": [
            {
                "positionValueType": 100,
                "issueId": "DRAM",
                "issueName": "Some fractional ETF",
                "instrumentType": 100,
                "quantity": 456.679,
                "averagePrice": 871.9,
                "lastPrice": 834.07,
                "closePrice": 852.21,
                "weightedAveragePrice": 0.0,
                "yieldValue": -17281.4,
                "marketValue": 380901.0,
                "dailyVariationPercentage": -0.02,
                "historicalVariationPercentage": -0.04,
                "averageCost": 398182.4,
                "positionPercentage": 1.0,
            }
        ],
        "efectivo": [],
        "totalPortfolioValue": [],
    }
    respx.post("https://homebroker-api.gbm.com/GBMP/api/Portfolio/GetPositionSummary").mock(
        return_value=httpx.Response(200, json=extended_response)
    )

    s = Positions(http).summary(LEGACY_ID, account_id="acct-uuid-1")
    assert len(s.sociedades_inversion_comun) == 1
    assert s.sociedades_inversion_comun[0].issue_id == "GBMAAA BO"
    assert len(s.mercado_extranjero) == 1
    assert s.mercado_extranjero[0].issue_id == "DRAM"
    # real_positions includes the new sections.
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


# ----------------------------------------------------------------------
# Dividends
# ----------------------------------------------------------------------
DIVIDENDS_URL = f"https://api.appgbm.com/v2/trading/contracts/{CONTRACT_ID}/transactions"


@respx.mock
def test_dividends_list_for_range_single_page(http: HttpClient) -> None:
    respx.get(DIVIDENDS_URL).mock(return_value=httpx.Response(200, json=DIVIDENDS_THREE_ITEMS))
    out = Dividends(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 1, 1), _dt.date(2026, 5, 22)
    )
    assert len(out) == 3
    assert {d.security_id for d in out} == {"FMX 23", "PINFRA *"}
    # Sorted chronologically by process_date.
    assert out[0].transaction_id == 24213656  # 14 May 14:00 UTC
    assert out[-1].transaction_id == 24286814  # 21 May 12:54 UTC


@respx.mock
def test_dividends_list_for_range_sends_correct_params(http: HttpClient) -> None:
    captured: dict[str, object] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=DIVIDENDS_THREE_ITEMS)

    respx.get(DIVIDENDS_URL).mock(side_effect=_capture)
    Dividends(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 1, 1), _dt.date(2026, 5, 22)
    )

    params = captured["params"]
    assert isinstance(params, dict)
    assert params["transac_type"] == "dividend"
    assert params["legacy_contracts_id"] == LEGACY_ID
    assert params["start_date"] == "2026-01-01"
    assert params["end_date"] == "2026-05-22"
    assert params["page"] == "1"


@respx.mock
def test_dividends_list_for_range_follows_pagination(http: HttpClient) -> None:
    """When ``pagination_metadata.next`` is non-empty, we keep iterating."""
    page1 = dividends_page(
        [DIVIDENDS_THREE_ITEMS["items"][0]],
        page=1,
        has_next=True,
    )
    page2 = dividends_page(
        [DIVIDENDS_THREE_ITEMS["items"][1], DIVIDENDS_THREE_ITEMS["items"][2]],
        page=2,
        has_next=False,
    )
    respx.get(DIVIDENDS_URL).mock(
        side_effect=[
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
    )
    out = Dividends(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 1, 1), _dt.date(2026, 5, 22)
    )
    assert len(out) == 3


@respx.mock
def test_dividends_dedupes_by_transaction_id(http: HttpClient) -> None:
    """Defensive: if pagination overlaps, we don't double-count."""
    page1 = dividends_page([DIVIDENDS_THREE_ITEMS["items"][0]], page=1, has_next=True)
    page2 = dividends_page(
        [DIVIDENDS_THREE_ITEMS["items"][0], DIVIDENDS_THREE_ITEMS["items"][1]],
        page=2,
        has_next=False,
    )
    respx.get(DIVIDENDS_URL).mock(
        side_effect=[
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
    )
    out = Dividends(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 1, 1), _dt.date(2026, 5, 22)
    )
    assert len(out) == 2  # not 3


def test_dividends_rejects_inverted_range(http: HttpClient) -> None:
    with pytest.raises(ValueError, match="from_date"):
        Dividends(http).list_for_range(
            CONTRACT_ID, LEGACY_ID, _dt.date(2026, 5, 15), _dt.date(2026, 5, 14)
        )


def test_dividend_is_withholding_property() -> None:
    """ISR rows should be classified as withholding."""
    from gbm_mx_api.domain.dividend import Dividend

    payout = Dividend.model_validate(DIVIDENDS_THREE_ITEMS["items"][1])
    isr = Dividend.model_validate(DIVIDENDS_THREE_ITEMS["items"][2])
    assert payout.is_withholding is False
    assert isr.is_withholding is True


# ----------------------------------------------------------------------
# Transactions
# ----------------------------------------------------------------------
TRANSACTIONS_URL = f"https://api.appgbm.com/v2/trading/contracts/{CONTRACT_ID}/transactions"


@respx.mock
def test_transactions_list_for_range_single_page(http: HttpClient) -> None:
    respx.get(TRANSACTIONS_URL).mock(return_value=httpx.Response(200, json=TRANSACTIONS_MIXED))
    out = Transactions(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 5, 1), _dt.date(2026, 5, 31)
    )
    assert len(out) == 11
    # Sorted ascending by process_date.
    assert out[0].process_date < out[-1].process_date


@respx.mock
def test_transactions_does_not_send_transac_type(http: HttpClient) -> None:
    """Backend ignores transac_type (except 'dividend'). We don't send it."""
    captured: dict[str, object] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=TRANSACTIONS_MIXED)

    respx.get(TRANSACTIONS_URL).mock(side_effect=_capture)
    Transactions(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 5, 1), _dt.date(2026, 5, 31)
    )

    params = captured["params"]
    assert isinstance(params, dict)
    assert "transac_type" not in params
    assert params["legacy_contracts_id"] == LEGACY_ID
    assert params["start_date"] == "2026-05-01"
    assert params["end_date"] == "2026-05-31"


@respx.mock
def test_transactions_follows_pagination(http: HttpClient) -> None:
    page1 = dividends_page([TRANSACTIONS_MIXED["items"][0]], page=1, has_next=True)
    page2 = dividends_page(TRANSACTIONS_MIXED["items"][1:3], page=2, has_next=False)
    respx.get(TRANSACTIONS_URL).mock(
        side_effect=[
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
    )
    out = Transactions(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 5, 1), _dt.date(2026, 5, 31)
    )
    assert len(out) == 3


@respx.mock
def test_transactions_dedupes_by_transaction_id(http: HttpClient) -> None:
    page1 = dividends_page([TRANSACTIONS_MIXED["items"][0]], page=1, has_next=True)
    page2 = dividends_page(
        [TRANSACTIONS_MIXED["items"][0], TRANSACTIONS_MIXED["items"][1]],
        page=2,
        has_next=False,
    )
    respx.get(TRANSACTIONS_URL).mock(
        side_effect=[
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
    )
    out = Transactions(http).list_for_range(
        CONTRACT_ID, LEGACY_ID, _dt.date(2026, 5, 1), _dt.date(2026, 5, 31)
    )
    assert len(out) == 2


def test_transactions_rejects_inverted_range(http: HttpClient) -> None:
    with pytest.raises(ValueError, match="from_date"):
        Transactions(http).list_for_range(
            CONTRACT_ID, LEGACY_ID, _dt.date(2026, 5, 31), _dt.date(2026, 5, 1)
        )


def test_transaction_category_classification() -> None:
    """Each fixture row maps to its expected category."""
    items = TRANSACTIONS_MIXED["items"]
    by_id = {item["transaction_id"]: Transaction.model_validate(item) for item in items}

    assert by_id[1001].category == "buy_stock"
    assert by_id[1002].category == "sell_stock"
    assert by_id[1003].category == "buy_fund"
    assert by_id[1004].category == "sell_fund"
    assert by_id[1005].category == "repo_buy"
    assert by_id[1006].category == "repo_mature"
    assert by_id[1007].category == "deposit"
    assert by_id[1008].category == "withdrawal"
    assert by_id[1009].category == "fx"
    assert by_id[1010].category == "dividend"
    assert by_id[1011].category == "tax_withholding"


def test_transaction_is_buy_is_sell_is_cash_flow() -> None:
    items = TRANSACTIONS_MIXED["items"]
    by_id = {item["transaction_id"]: Transaction.model_validate(item) for item in items}

    assert by_id[1001].is_buy is True and by_id[1001].is_sell is False
    assert by_id[1004].is_sell is True and by_id[1004].is_buy is False
    assert by_id[1006].is_sell is True  # repo_mature counts as sell-like
    assert by_id[1007].is_cash_flow is True
    assert by_id[1008].is_cash_flow is True
    assert by_id[1009].is_cash_flow is False  # fx is its own bucket
    assert by_id[1010].is_buy is False and by_id[1010].is_sell is False
