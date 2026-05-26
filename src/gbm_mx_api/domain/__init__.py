"""Typed domain models.

Re-exports the public types so callers can do::

    from gbm_mx_api.domain import (
        Account, Contract, FilledOrder, Order, OrderStatus, Side, Position,
    )
"""

from __future__ import annotations

from gbm_mx_api.domain.account import Account, Money
from gbm_mx_api.domain.contract import Contract
from gbm_mx_api.domain.dividend import Dividend
from gbm_mx_api.domain.enums import (
    AccountType,
    InstrumentType,
    OrderStatus,
    PositionValueType,
    Side,
)
from gbm_mx_api.domain.order import FilledOrder, Order
from gbm_mx_api.domain.position import PortfolioSummary, Position
from gbm_mx_api.domain.transaction import Transaction

__all__ = [
    "Account",
    "AccountType",
    "Contract",
    "Dividend",
    "FilledOrder",
    "InstrumentType",
    "Money",
    "Order",
    "OrderStatus",
    "PortfolioSummary",
    "Position",
    "PositionValueType",
    "Side",
    "Transaction",
]
