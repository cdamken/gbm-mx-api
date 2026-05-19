"""Enums that mirror the magic integers used by GBM's internal API.

Discovered during Phase 0 reverse engineering. Members map to the literal
integer values the backend uses. Unknown values raise on parsing — if you
hit one, add it here and open an issue / PR.
"""

from __future__ import annotations

from enum import IntEnum


class OrderStatus(IntEnum):
    """Mirrors blotter ``gbmIntProcessStatus``."""

    CANCELLED = 5
    FILLED = 7

    @property
    def is_filled(self) -> bool:
        return self is OrderStatus.FILLED


class Side(IntEnum):
    """Buy/sell side of an order.

    The backend uses a boolean ``bitBuy`` rather than an enum, but we model it
    as an enum here for symmetry.
    """

    BUY = 1
    SELL = 0

    @classmethod
    def from_bit_buy(cls, value: bool) -> Side:
        return cls.BUY if value else cls.SELL


class InstrumentType(IntEnum):
    """Mirrors blotter ``instrumentType`` (also used in ``instrumentTypes`` filter)."""

    BMV = 0  # IPC and other Mexican equities
    SIC = 2  # Stocks listed via the international quotation system (US tickers)


class AccountType(str):
    """Values seen for ``management_type_template`` in ``/v2/...accounts``.

    Modeled as ``str`` constants rather than ``StrEnum`` to keep round-tripping
    simple and forward-compatible (new account types from GBM won't break
    parsing — we just won't recognize them yet).
    """

    TRADING = "trading"  # Bolsa Mexicana (BMV)
    TRADING_USA = "trading_usa"  # SIC fractional shares
    SMART_CASH = "smart_cash"  # Money market fund


class PositionValueType(IntEnum):
    """Section identifier inside the position summary payload.

    Values are inferred from real responses across different account types.
    Add new ones here if a future account surfaces a different value.
    """

    SIC = 0
    BMV = 1
    COMUN = 2  # Sociedades de inversión común (e.g. GBMAAA BO)
    DEUDA = 5  # Sociedades de inversión de deuda (fondos)
    EFECTIVO = 27
    EXTRANJERO = 100  # Trading USA — fractional shares of foreign equities
    TOTAL = 1000
