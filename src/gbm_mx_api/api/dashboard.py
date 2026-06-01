"""``api.appgbm.com/v3/dashboard/...`` — the mobile-app dashboard aggregates.

Distinct from the legacy account/position endpoints: this returns the
exact "Total Invertido" number the user sees on the GBM mobile and
web apps, computed server-side with the most current FX rate.
"""

from __future__ import annotations

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.investments_groups import InvestmentsGroups
from gbm_mx_api.errors import ApiError


def _investments_groups_url(contract_id: str) -> str:
    return f"https://api.appgbm.com/v3/dashboard/contracts/{contract_id}/investments-groups"


class Dashboard(ApiBase):
    """Aggregate endpoints under ``api.appgbm.com/v3/dashboard``."""

    def investments_groups(self, contract_id: str, email: str) -> InvestmentsGroups:
        """The top-level dashboard summary.

        Returns the "total_position.amount" (= "TOTAL INVERTIDO" in the
        mobile app's home screen) plus a per-group breakdown. The five
        groups for a typical Mexican user are:

        - ``smart_cash`` — Smart Cash MXN money-market fund.
        - ``smart_cash_usd`` — Smart Cash Dólares (USD money-market).
        - ``instruments`` — Trading MX (BMV + SIC) aggregated across all
          trading accounts (Personal + Asesor).
        - ``offshore`` — Trading USA (fractional shares).
        - ``goals`` — GBM Advisory.

        Args:
            contract_id: ``Contract.contract_id`` (UUID).
            email: User's email — the backend uses it as a join key.
                Required by the backend; without it the response is
                rejected.
        """
        # This endpoint is consistently slow (5-30 seconds) because it
        # joins data across the legacy homebroker, the offshore broker,
        # and live FX. Bump the timeout to 60s so a normal-day fetch
        # doesn't trip the 15s default.
        body = self._http.get(
            _investments_groups_url(contract_id),
            params={"email": email},
            timeout=60.0,
        )
        if not isinstance(body, dict):
            raise ApiError(
                f"Unexpected /investments-groups shape: {type(body).__name__}",
                status_code=200,
                body=body,
            )
        return InvestmentsGroups.model_validate(body)
