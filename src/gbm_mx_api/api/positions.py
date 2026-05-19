"""``/GBMP/api/Portfolio/GetPositionSummary`` — current portfolio snapshot."""

from __future__ import annotations

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.position import PortfolioSummary
from gbm_mx_api.errors import ApiError

POSITION_SUMMARY_URL = "https://homebroker-api.gbm.com/GBMP/api/Portfolio/GetPositionSummary"


class Positions(ApiBase):
    """Position-related endpoints on the legacy homebroker backend."""

    def summary(self, legacy_account_id: str) -> PortfolioSummary:
        """Return the full portfolio composition for one account.

        Args:
            legacy_account_id: ``Account.legacy_contract_id`` (e.g. ``EP47NC05``).
        """
        body = self._http.post(POSITION_SUMMARY_URL, json={"request": legacy_account_id})
        if not isinstance(body, dict):
            raise ApiError(
                f"Unexpected GetPositionSummary shape: {type(body).__name__}",
                status_code=200,
                body=body,
            )
        return PortfolioSummary.model_validate(body)
