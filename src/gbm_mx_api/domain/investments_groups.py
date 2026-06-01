"""Investments-groups (dashboard aggregates) — the source of "Total Invertido".

Discovered via DevTools HAR on 2026-06-01. The GBM mobile/web app shows
"TOTAL INVERTIDO $804,XXX.XX" calculated server-side at the
``api.appgbm.com/v3/dashboard/...`` endpoint and returned in this shape.

Why this matters: the legacy ``/GBMP/Portfolio/GetPositionSummary`` and
``/v2/contracts/{id}/accounts`` endpoints both produce account market
values using one FX rate snapshot, while this v3 endpoint uses a more
current FX rate. For Carlos's portfolio (with $28k USD in DRAM) the
two diverge by ~$1,000 MXN over a typical day. This v3 endpoint
matches what the user sees in the GBM mobile app to the cent.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    """Currency-aware amount as the v3 dashboard endpoint returns it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    amount: Decimal
    currency: str = "MXN"


class Group(BaseModel):
    """One investments-group (= account in the user's UI).

    The ``type`` discriminates the kind of group: ``smart_cash``,
    ``smart_cash_usd``, ``instruments`` (= Trading MX, both Personal
    and Asesor aggregated), ``offshore`` (= Trading USA), or ``goals``
    (= GBM Advisory).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(description='"Smart Cash", "Trading USA", etc.')
    type: str = Field(
        description=(
            "Group discriminator: smart_cash | smart_cash_usd | instruments | offshore | goals."
        )
    )
    status: str = "active"
    position: Position | None = Field(
        default=None,
        description="Current market value of the group (MXN).",
    )
    positions: dict[str, Position] | None = Field(
        default=None,
        description=(
            "Per-currency breakdown (only present on groups that hold USD: "
            "Trading USA, Smart Cash Dólares, GBM Advisory)."
        ),
    )
    plus_minus: Position | None = Field(default=None, description="P&L in money (MXN).")
    plus_minus_percentage: float | None = Field(default=None)


class InvestmentsGroups(BaseModel):
    """Top-level dashboard aggregate — drives the "TOTAL INVERTIDO" card."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    total_position: Position = Field(
        description="Sum across all groups, in MXN. THIS is what GBM displays."
    )
    groups: list[Group] = Field(default_factory=list)
