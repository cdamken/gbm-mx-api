"""Generic transaction model — every cash / security movement from the ledger.

Discovered via DevTools on ``appgbm.com`` (2026-05). The backend endpoint is

    GET https://api.appgbm.com/v2/trading/contracts/{contract_id}/transactions
        ?start_date=...&end_date=...&legacy_contracts_id=...&page=1&page_size=100

The endpoint returns **every** movement booked against a legacy account:
stock buys/sells (``transaction_type="capitales"``), money-market activity
(``"mercado_dinero"``), cash transfers (``"tesoreria"``), FX
(``"divisas"``), and dividend-style entries (``"prestamo_valores"``). The
existing :class:`gbm_mx_api.domain.dividend.Dividend` model is a narrower
view of the same payload kept for backward compatibility.

The ``transac_type`` query parameter is essentially **ignored** by the
backend (all values except ``"dividend"`` return the same full result),
so this library does not expose it — fetch everything and let the
consumer filter.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    """A single ledger row — security operation or cash movement."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    transaction_id: int = Field(description="Unique row id from GBM's ledger.")
    contract_id: str = Field(description="UUID of the contract.")
    legacy_contract_id: str = Field(description='e.g. "EP47NC05".')
    security_id: str = Field(
        default="",
        description='Ticker / security code (e.g. "FMX 23"); empty for pure cash flows.',
    )
    security_name: str = Field(default="", description="Issuer full name (truncated).")
    transaction_type: str = Field(
        description=(
            "Bucket assigned by GBM. Observed values: "
            '"capitales" (BMV/SIC stocks), "mercado_dinero" (funds + repos), '
            '"tesoreria" (cash transfers), "divisas" (FX), '
            '"prestamo_valores" (dividend-style entries).'
        )
    )
    sub_transaction_type: int = Field(
        default=0, description="Numeric sub-classifier; opaque per type."
    )
    transaction_description: str = Field(
        description=(
            "Human-readable description. Examples: "
            '"Compra de Acciones.", "Venta de Acciones.", '
            '"Venta Soc.de Inv.- Cliente", "RETIRO DE EFECTIVO POR TRASPASO", '
            '"DEPOSITO DE EFECTIVO POR TRASPASO", "Compra en Reporto", '
            '"Vencimiento de Reporto", "Abono Efectivo Dividendo, Cust. Normal".'
        )
    )
    transaction_amount: Decimal = Field(description="Gross amount (MXN).")
    transaction_net_amount: Decimal = Field(description="Net amount after taxes (MXN).")
    quantity: Decimal = Field(default=Decimal("0"))
    transaction_price: Decimal = Field(default=Decimal("0"))
    transaction_commission: Decimal = Field(default=Decimal("0"))
    transaction_tax: Decimal = Field(default=Decimal("0"))
    transaction_interest: Decimal = Field(default=Decimal("0"))
    transaction_yield_rate: Decimal = Field(default=Decimal("0"))
    transaction_term: Decimal = Field(default=Decimal("0"))
    process_date: datetime = Field(description="Date the event was booked.")
    settlement_date: datetime | None = Field(default=None)
    transaction_time: str = Field(default="", description='"HH:MM:SS" string.')

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------
    # GBM's ``transaction_type`` discriminates the bucket; the
    # ``transaction_description`` carries the buy/sell intent. We combine
    # both because neither alone is enough (e.g. ``capitales`` covers buys
    # AND sells; ``mercado_dinero`` covers fund buys, fund sells, AND repo
    # ops, etc).

    @property
    def category(self) -> str:
        """Coarse-grained category for display & filtering.

        One of:

        - ``"buy_stock"`` — Compra de Acciones (capitales).
        - ``"sell_stock"`` — Venta de Acciones (capitales).
        - ``"buy_fund"`` — Compra Soc. de Inv. (mercado_dinero).
        - ``"sell_fund"`` — Venta Soc. de Inv. (mercado_dinero).
        - ``"repo_buy"`` — Compra en Reporto (mercado_dinero).
        - ``"repo_mature"`` — Vencimiento de Reporto (mercado_dinero).
        - ``"deposit"`` — Depósito de efectivo por traspaso (tesoreria).
        - ``"withdrawal"`` — Retiro de efectivo por traspaso (tesoreria).
        - ``"fx"`` — Compra/venta de divisas.
        - ``"dividend"`` — Abono Efectivo Dividendo / Reembolso de Capital
          / Resultado Fiscal Distribuido.
        - ``"tax_withholding"`` — ISR retenido por la propia GBM.
        - ``"other"`` — fallback.
        """
        desc = self.transaction_description.lower()
        ttype = self.transaction_type.lower()

        # Tax withholding wins over everything (descriptions like
        # "ISR Cedular por Dividendos" can otherwise be confused with
        # dividend payouts).
        if "isr" in desc or "retención" in desc or "retencion" in desc:
            return "tax_withholding"

        if ttype == "capitales":
            if "venta" in desc:
                return "sell_stock"
            if "compra" in desc:
                return "buy_stock"
        if ttype == "mercado_dinero":
            if "vencimiento" in desc and "reporto" in desc:
                return "repo_mature"
            if "compra en reporto" in desc:
                return "repo_buy"
            if "venta" in desc:
                return "sell_fund"
            if "compra" in desc:
                return "buy_fund"
        if ttype == "tesoreria":
            if "deposito" in desc or "depósito" in desc:
                return "deposit"
            if "retiro" in desc:
                return "withdrawal"
        if ttype == "divisas":
            return "fx"
        if ttype == "prestamo_valores":
            # Real dividend cash inflows: "Abono Efectivo Dividendo",
            # "Abono Reembolso de Capital", "Resultado Fiscal Distribuido".
            return "dividend"
        return "other"

    @property
    def is_buy(self) -> bool:
        return self.category in ("buy_stock", "buy_fund", "repo_buy")

    @property
    def is_sell(self) -> bool:
        return self.category in ("sell_stock", "sell_fund", "repo_mature")

    @property
    def is_cash_flow(self) -> bool:
        return self.category in ("deposit", "withdrawal")
