"""Dividend / cash-distribution models.

Discovered via reverse engineering of ``appgbm.com``'s "Dividendos" tab
(2026-05). The backend endpoint is

    GET https://api.appgbm.com/v2/trading/contracts/{contract_id}/transactions
        ?transac_type=dividend&start_date=...&end_date=...
          &legacy_contracts_id=...&page=1&page_size=50

The shape returned bundles *every* cash-flow that GBM classifies as a
dividend in their accounting: cash dividend payments, capital returns,
the corresponding ISR withholding lines, "Resultado Fiscal Distribuido"
(distributed taxable income from funds), etc. The library exposes them
as a single :class:`Dividend` model — the consumer can filter by
``transaction_description`` if they only want the "happy" cash inflows.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Dividend(BaseModel):
    """A single cash distribution event.

    Fields are aliased to the snake_case keys the backend returns. The
    model is intentionally permissive (``extra="ignore"``) because the
    backend frequently extends payloads.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    transaction_id: int = Field(description="Unique row id from GBM's ledger.")
    contract_id: str = Field(description="UUID of the contract.")
    legacy_contract_id: str = Field(description='e.g. "EP47NC05".')
    security_id: str = Field(description='Ticker / security code, e.g. "FMX 23".')
    security_name: str = Field(default="", description="Issuer full name (truncated).")
    transaction_type: str = Field(
        description=(
            'Bucket assigned by GBM, e.g. "prestamo_valores". '
            "For dividend rows this label is mostly noise — use "
            ":attr:`transaction_description` to know what the cash flow is."
        )
    )
    sub_transaction_type: int = Field(
        default=0, description="Numeric sub-classifier; mostly opaque."
    )
    transaction_description: str = Field(
        description=(
            "Human-readable description of the cash movement. Examples: "
            '"Abono Efectivo Dividendo, Cust. Normal", '
            '"Abono Reembolso de Capital, Cust. Normal", '
            '"ISR Cedular por Dividendos".'
        )
    )
    transaction_amount: Decimal = Field(description="Gross amount (MXN).")
    transaction_net_amount: Decimal = Field(description="Net amount after applicable taxes (MXN).")
    quantity: Decimal = Field(
        default=Decimal("0"),
        description="Shares involved (zero for pure cash flows).",
    )
    transaction_price: Decimal = Field(default=Decimal("0"))
    transaction_commission: Decimal = Field(default=Decimal("0"))
    transaction_tax: Decimal = Field(default=Decimal("0"))
    transaction_interest: Decimal = Field(default=Decimal("0"))
    transaction_yield_rate: Decimal = Field(default=Decimal("0"))
    transaction_term: Decimal = Field(default=Decimal("0"))
    process_date: datetime = Field(description="Date the event was booked.")
    settlement_date: datetime | None = Field(
        default=None, description="Settlement date if available."
    )
    transaction_time: str = Field(default="", description='"HH:MM:SS" string.')

    @property
    def is_withholding(self) -> bool:
        """True for the ISR (tax-withholding) lines that accompany payouts.

        The Dividendos tab on appgbm.com lists both the gross payout AND
        the ISR withholding as separate rows under the same security.
        """
        desc = self.transaction_description.lower()
        return "isr" in desc or "retención" in desc or "retencion" in desc
