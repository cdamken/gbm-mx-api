"""Portfolio position models.

The ``GetPositionSummary`` endpoint returns positions grouped into named
sections (SIC, BMV, deuda, efectivo, total). This module models both the
individual position and the full summary.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from gbm_mx_api.domain.enums import PositionValueType


class Position(BaseModel):
    """One position line within the portfolio summary."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    issue_id: str = Field(alias="issueId", description="Ticker or pseudo-ticker.")
    issue_name: str | None = Field(default=None, alias="issueName")
    position_value_type: PositionValueType = Field(alias="positionValueType")
    instrument_type: int = Field(alias="instrumentType", description="Raw int from API.")
    quantity: Decimal
    average_price: Decimal = Field(alias="averagePrice")
    last_price: Decimal = Field(alias="lastPrice")
    close_price: Decimal = Field(alias="closePrice")
    yield_value: Decimal = Field(alias="yieldValue", description="P&L on the position.")
    market_value: Decimal = Field(alias="marketValue")
    daily_variation_percentage: Decimal = Field(alias="dailyVariationPercentage")
    historical_variation_percentage: Decimal = Field(alias="historicalVariationPercentage")
    average_cost: Decimal = Field(alias="averageCost")
    position_percentage: Decimal = Field(
        alias="positionPercentage", description="Weight in portfolio (0..1)."
    )

    @property
    def is_subtotal(self) -> bool:
        """Each section ends with a synthetic ``Subtotal`` line."""
        return self.issue_id == "Subtotal"


class PortfolioSummary(BaseModel):
    """Full position summary as returned by ``GetPositionSummary``.

    The five buckets are typed lists. The synthetic ``Subtotal`` entries the
    backend ships at the end of each section are kept (with ``is_subtotal``
    True) so callers can either filter them out or use them directly.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    mercados_globales_sic: list[Position] = Field(default_factory=list, alias="mercadosGlobalesSIC")
    mercado_capitales: list[Position] = Field(default_factory=list, alias="mercadoCapitales")
    sociedades_inversion_deuda: list[Position] = Field(
        default_factory=list, alias="sociedadesInversionDeuda"
    )
    efectivo: list[Position] = Field(default_factory=list)
    total_portfolio_value: list[Position] = Field(default_factory=list, alias="totalPortfolioValue")

    # --- helpers -------------------------------------------------------
    @property
    def real_positions(self) -> list[Position]:
        """All non-subtotal positions across SIC + BMV + funds."""
        return [
            p
            for section in (
                self.mercados_globales_sic,
                self.mercado_capitales,
                self.sociedades_inversion_deuda,
            )
            for p in section
            if not p.is_subtotal
        ]

    @property
    def total_market_value(self) -> Decimal:
        """Sum from the ``totalPortfolioValue`` section (single entry)."""
        if not self.total_portfolio_value:
            return Decimal("0")
        return self.total_portfolio_value[0].market_value
