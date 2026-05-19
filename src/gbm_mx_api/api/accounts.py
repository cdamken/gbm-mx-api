"""``/v2/contracts/{contract_id}/accounts`` — list strategies."""

from __future__ import annotations

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.account import Account
from gbm_mx_api.domain.enums import AccountType
from gbm_mx_api.errors import ApiError


def _accounts_url(contract_id: str) -> str:
    return f"https://api.gbm.com/v2/contracts/{contract_id}/accounts"


class Accounts(ApiBase):
    """Endpoints under ``api.gbm.com/v2/contracts/{id}/accounts``."""

    def list(self, contract_id: str) -> list[Account]:
        """Every active strategy of the given contract.

        Args:
            contract_id: ``Contract.contract_id`` (UUID).
        """
        body = self._http.get(_accounts_url(contract_id))
        if not isinstance(body, list):
            raise ApiError(
                f"Unexpected /accounts shape: {type(body).__name__}",
                status_code=200,
                body=body,
            )
        return [Account.model_validate(item) for item in body]

    def get_trading(self, contract_id: str) -> Account:
        """First active ``trading`` (BMV) account, raising if none.

        Useful because ``Portfolio.md`` tracks only the BMV trading
        strategy. Add equivalents for ``trading_usa`` etc. if needed.
        """
        for acct in self.list(contract_id):
            if acct.management_type_template == AccountType.TRADING and acct.status == "active":
                return acct
        raise ApiError("No active 'trading' account found.", status_code=200)
