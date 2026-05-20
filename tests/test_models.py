"""Tests for Pydantic domain models against representative GBM responses."""

from __future__ import annotations

from decimal import Decimal

import pytest

from gbm_mx_api.domain import (
    Account,
    Contract,
    FilledOrder,
    InstrumentType,
    Order,
    OrderStatus,
    PortfolioSummary,
    Side,
)
from tests.fixtures import (
    ACCOUNTS_RESPONSE,
    BLOTTER_TWO_ORDERS,
    CONTRACTS_RESPONSE,
    POSITION_SUMMARY_RESPONSE,
)


# ----------------------------------------------------------------------
# Contract
# ----------------------------------------------------------------------
def test_contract_parses_real_shape() -> None:
    c = Contract.model_validate(CONTRACTS_RESPONSE[0])
    assert c.contract_id == "00000000-0000-4000-8000-000000000001"
    assert c.legacy_contract_id == "AB12CD"
    assert c.contract_status == "active"
    assert c.is_legacy is False
    # PII fields are intentionally absent on the model
    assert not hasattr(c, "first_name")
    assert not hasattr(c, "last_name")


# ----------------------------------------------------------------------
# Account
# ----------------------------------------------------------------------
def test_account_parses_with_nested_money() -> None:
    a = Account.model_validate(ACCOUNTS_RESPONSE[0])
    assert a.account_id == "00000000-0000-4000-8000-000000000010"
    assert a.legacy_contract_id == "AB12CD05"
    assert a.management_type_template == "trading"
    assert a.position is not None and a.position.amount == Decimal("151536.95")
    assert a.position.currency == "MXN"
    assert a.plus_minus is not None and a.plus_minus.amount == Decimal("3292.88")


# ----------------------------------------------------------------------
# Order / FilledOrder
# ----------------------------------------------------------------------
def test_order_parses_filled() -> None:
    raw = BLOTTER_TWO_ORDERS["ordersList"][0]
    o = Order.model_validate(raw)
    assert o.sob_id == 109142599
    assert o.issue_id == "WDC *"
    assert o.status == OrderStatus.FILLED.value
    assert o.is_filled
    assert o.instrument_type is InstrumentType.SIC
    assert o.bit_buy is True
    assert o.side is Side.BUY
    assert o.is_filled
    assert o.average_price == Decimal("8692.24")
    assert o.commission == Decimal("21.73")


def test_order_parses_cancelled() -> None:
    raw = BLOTTER_TWO_ORDERS["ordersList"][1]
    o = Order.model_validate(raw)
    assert o.status == OrderStatus.CANCELLED.value
    assert o.is_cancelled
    assert not o.is_filled
    assert not o.is_filled
    with pytest.raises(ValueError, match="not FILLED"):
        o.to_filled()


def test_to_filled_projection() -> None:
    o = Order.model_validate(BLOTTER_TWO_ORDERS["ordersList"][0])
    f = o.to_filled()
    assert isinstance(f, FilledOrder)
    assert f.sob_id == o.sob_id
    assert f.quantity == 1
    assert f.average_price == Decimal("8692.24")
    assert f.amount == Decimal("8692.24")
    assert f.commission == Decimal("21.73")


def test_status_accepts_string_int() -> None:
    """Defensive: backend has been observed serializing status as a string."""
    raw = dict(BLOTTER_TWO_ORDERS["ordersList"][0])
    raw["gbmIntProcessStatus"] = "7"
    o = Order.model_validate(raw)
    assert o.status == OrderStatus.FILLED.value
    assert o.is_filled


def test_status_accepts_unknown_value() -> None:
    """Unknown statuses (e.g. 3 = pending, partial fill) should not crash."""
    raw = dict(BLOTTER_TWO_ORDERS["ordersList"][0])
    raw["gbmIntProcessStatus"] = 3
    o = Order.model_validate(raw)
    assert o.status == 3
    assert not o.is_filled
    assert not o.is_cancelled
    assert o.status_label == "Estado 3"


def test_status_label_known_values() -> None:
    """Known statuses (5/7) get the Spanish name."""
    raw_filled = dict(BLOTTER_TWO_ORDERS["ordersList"][0])
    raw_filled["gbmIntProcessStatus"] = 7
    assert Order.model_validate(raw_filled).status_label == "Filled"

    raw_cancelled = dict(BLOTTER_TWO_ORDERS["ordersList"][0])
    raw_cancelled["gbmIntProcessStatus"] = 5
    assert Order.model_validate(raw_cancelled).status_label == "Cancelled"


# ----------------------------------------------------------------------
# PortfolioSummary
# ----------------------------------------------------------------------
def test_portfolio_summary_parses_five_buckets() -> None:
    s = PortfolioSummary.model_validate(POSITION_SUMMARY_RESPONSE)
    assert len(s.mercados_globales_sic) == 2  # 1 real + 1 subtotal
    assert len(s.mercado_capitales) == 1
    assert s.efectivo == []
    assert s.total_market_value == Decimal("151405.11")
    # real_positions excludes subtotals
    real = s.real_positions
    issues = {p.issue_id for p in real}
    assert "Subtotal" not in issues
    assert "AMD *" in issues
    assert "NAFTRAC ISHRS" in issues
