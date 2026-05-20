"""Order models.

Two layers:

- :class:`Order` mirrors the raw blotter shape from
  ``POST /GBMP/api/Operation/GetBlotterOrders``. All fields are present.
- :class:`FilledOrder` is a tidy projection over an :class:`Order` whose
  status is :attr:`OrderStatus.FILLED`. It carries only the fields that the
  consumers actually need (and that we know how to interpret).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gbm_mx_api.domain.enums import InstrumentType, OrderStatus, Side


class Order(BaseModel):
    """Raw blotter order entry.

    Fields are aliased to the camelCase keys the backend returns. The model
    is intentionally permissive (``extra="ignore"``) because the backend
    may add new fields at any time.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    sob_id: int = Field(alias="sobId", description="Unique order id (matches email).")
    account_id: str = Field(alias="accountId", description="e.g. 'EP47NC05'.")
    issue_id: str = Field(alias="issueId", description="Ticker / instrument code.")
    instrument_type: InstrumentType = Field(alias="instrumentType")
    status: int = Field(
        alias="gbmIntProcessStatus",
        description=(
            "Raw GBM order status code. Known values: "
            "5=Cancelada, 7=Llena. Other ints come from the backend "
            "(pending, partially-filled, etc.) and are accepted as-is."
        ),
    )
    bit_buy: bool = Field(alias="bitBuy", description="True=buy, false=sell.")
    original_quantity: int = Field(alias="originalQuantity")
    assigned_quantity: int = Field(alias="assignedQuantity")
    cancel_quantity: int = Field(alias="cancelQuantity")
    average_price: Decimal = Field(alias="averagePrice")
    price: Decimal = Field(description="Limit price submitted.")
    commission: Decimal = Field(alias="commision", description="Commission charged (MXN).")
    iva: Decimal = Field(default=Decimal("0"), description="VAT over commission.")
    process_date: datetime = Field(alias="processDate")
    is_cancelable: bool = Field(alias="isCancelable", default=False)
    cancel_message: str = Field(alias="cancelMessage", default="")

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: object) -> object:
        # Backend sometimes ships as int, sometimes as string-of-int.
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v

    @property
    def side(self) -> Side:
        return Side.from_bit_buy(self.bit_buy)

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED.value

    @property
    def is_cancelled(self) -> bool:
        return self.status == OrderStatus.CANCELLED.value

    @property
    def status_label(self) -> str:
        """Spanish-friendly label for the status code.

        Known: 5=Cancelada, 7=Llena. Unknown statuses surface as
        ``"Estado N"`` so the UI can still show something instead of
        crashing.
        """
        try:
            return OrderStatus(self.status).name.title()
        except ValueError:
            return f"Estado {self.status}"

    def to_filled(self) -> FilledOrder:
        """Project to :class:`FilledOrder`.

        Raises:
            ValueError: if this order is not in FILLED state.
        """
        if not self.is_filled:
            raise ValueError(f"Order {self.sob_id} is not FILLED (status={self.status}).")
        return FilledOrder(
            sob_id=self.sob_id,
            account_id=self.account_id,
            issue_id=self.issue_id,
            instrument_type=self.instrument_type,
            side=self.side,
            quantity=self.assigned_quantity,
            average_price=self.average_price,
            commission=self.commission,
            iva=self.iva,
            processed_at=self.process_date,
        )


class FilledOrder(BaseModel):
    """A tidy, narrowed projection of a filled order.

    Carries only what downstream consumers need: the identifier (``sob_id``),
    instrument, side, quantity, price, fees, and the timestamp.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sob_id: int
    account_id: str
    issue_id: str
    instrument_type: InstrumentType
    side: Side
    quantity: int
    average_price: Decimal
    commission: Decimal
    iva: Decimal = Decimal("0")
    processed_at: datetime

    @property
    def amount(self) -> Decimal:
        """``quantity * average_price`` — the order's total (before fees)."""
        return self.quantity * self.average_price
