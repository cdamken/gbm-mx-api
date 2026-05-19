"""``/v1/contracts`` — list the user's contracts."""

from __future__ import annotations

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.contract import Contract
from gbm_mx_api.errors import ApiError

CONTRACTS_URL = "https://api.gbm.com/v1/contracts"


class Contracts(ApiBase):
    """Endpoints under ``api.gbm.com/v1/contracts``."""

    def list(self) -> list[Contract]:
        """Return every contract for the authenticated user (usually one)."""
        body = self._http.get(CONTRACTS_URL)
        if not isinstance(body, list):
            raise ApiError(
                f"Unexpected /v1/contracts shape: {type(body).__name__}",
                status_code=200,
                body=body,
            )
        return [Contract.model_validate(item) for item in body]

    def get_main(self) -> Contract:
        """Convenience: return the first contract (the typical case).

        Raises:
            ApiError: when the list is empty.
        """
        contracts = self.list()
        if not contracts:
            raise ApiError("No contracts returned for user.", status_code=200, body=[])
        return contracts[0]
