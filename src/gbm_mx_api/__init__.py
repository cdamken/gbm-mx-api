"""gbm-mx-api: unofficial Python client for the GBM+ brokerage API.

Public surface — import from here.
"""

from __future__ import annotations

from gbm_mx_api._sync import sync, try_refresh_saved
from gbm_mx_api._version import __version__
from gbm_mx_api.auth.session import Session
from gbm_mx_api.client import GbmClient
from gbm_mx_api.domain import (
    Account,
    AccountType,
    Contract,
    Dividend,
    FilledOrder,
    InstrumentType,
    Money,
    Order,
    OrderStatus,
    PortfolioSummary,
    Position,
    PositionValueType,
    Side,
)
from gbm_mx_api.errors import (
    ApiError,
    AuthError,
    GbmError,
    MfaRequired,
    RateLimited,
    TransportError,
)

__all__ = [
    "Account",
    "AccountType",
    "ApiError",
    "AuthError",
    "Contract",
    "Dividend",
    "FilledOrder",
    "GbmClient",
    "GbmError",
    "InstrumentType",
    "MfaRequired",
    "Money",
    "Order",
    "OrderStatus",
    "PortfolioSummary",
    "Position",
    "PositionValueType",
    "RateLimited",
    "Session",
    "Side",
    "TransportError",
    "__version__",
    "sync",
    "try_refresh_saved",
]
