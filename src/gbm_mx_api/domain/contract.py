"""Contract model — top-level identifier of a GBM customer relationship."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    """Represents one item of ``GET /v1/contracts``.

    A user typically has exactly one ``Contract``, but the API returns a list
    so we keep it explicit.

    Field names mirror the JSON keys (snake_case). The ``legacy_contract_id``
    here is the **general** legacy id without account suffix — for calls to
    the homebroker-api backend, use the per-account id from :class:`Account`.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    contract_id: str = Field(description="UUID identifying this contract.")
    legacy_contract_id: str = Field(description="Legacy id (no account suffix).")
    contract_status: str = Field(description="e.g. 'active'.")
    opening_type: str = Field(description="e.g. 'long_opening'.")
    is_legacy: bool = False
    is_migrated: bool = False
    is_dashboard_blocked: bool = False
    created_at: datetime | None = None

    # The /v1/contracts endpoint also includes the user's full name in the
    # response, but we intentionally drop those fields (PII) — they're not
    # needed by any downstream code and keeping them out makes accidental
    # logging safer.
