"""Account / strategy model — one entry from ``/v2/contracts/{id}/accounts``."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Money(BaseModel):
    """Currency-aware monetary amount as the backend returns it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    amount: Decimal
    currency: str = "MXN"


class Account(BaseModel):
    """One investment strategy within a contract.

    Each account has its own ``legacy_contract_id`` (with the account suffix
    appended to the contract's, e.g. ``EP47NC05``) which is what
    homebroker-api calls expect.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    account_id: str = Field(description="UUID identifying this account.")
    legacy_contract_id: str = Field(
        description="Per-account legacy id (e.g. 'EP47NC05'). Used by homebroker-api."
    )
    name: str | None = Field(default=None, description="User-chosen alias.")
    number: int | None = None
    management_type_template: str = Field(description="See AccountType constants for known values.")
    position: Money | None = Field(default=None, description="Current market value.")
    plus_minus: Money | None = Field(default=None, description="P&L in money.")
    plus_minus_percentage: float | None = Field(default=None, description="P&L as fraction.")
    status: str = "active"
    collecting_account: str | None = None
    profile_type: str | None = None
    created_at: datetime | None = None
