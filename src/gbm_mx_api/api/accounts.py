"""``/v2/contracts/{contract_id}/accounts`` — list strategies."""

from __future__ import annotations

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.account import Account
from gbm_mx_api.domain.enums import AccountType
from gbm_mx_api.errors import ApiError


def _accounts_url(contract_id: str) -> str:
    return f"https://api.gbm.com/v2/contracts/{contract_id}/accounts"


def _dashboard_accounts_url(contract_id: str) -> str:
    return f"https://api.appgbm.com/v1/dashboard/contracts/{contract_id}/accounts"


# Module-level alias so methods inside the class can annotate their
# return type without ``list[...]`` being shadowed by the
# ``Accounts.list`` method (which mypy resolves before the builtin).
_AccountList = list[Account]


class Accounts(ApiBase):
    """Endpoints under ``api.gbm.com/v2/contracts/{id}/accounts`` and the
    newer ``api.appgbm.com/v1/dashboard/contracts/{id}/accounts``."""

    def list(self, contract_id: str) -> list[Account]:
        """Every active strategy of the given contract, with balances.

        Uses the legacy ``api.gbm.com/v2`` endpoint that includes
        ``position`` and ``plus_minus`` per account. **Note:** this
        endpoint **omits** the Smart Cash USD (``wealth``) account; if
        you need the complete list (5 accounts incl. Smart Cash USD)
        use :meth:`list_with_dashboard`.

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

    def list_dashboard(self, contract_id: str) -> _AccountList:
        """Every account as the appgbm.com dashboard knows them — metadata only.

        Calls ``api.appgbm.com/v1/dashboard/contracts/{id}/accounts``.
        Returns the full set of accounts the user sees in the web/mobile
        app (5 in Carlos's case, including the Smart Cash Dólares account
        of type ``wealth`` that the legacy v2 endpoint omits).

        **No balance fields** are included on this endpoint — only the
        metadata (name, type, legacy id, ``is_smart_cash_usd``). Use
        :meth:`list_with_dashboard` to get balances merged in.
        """
        body = self._http.get(_dashboard_accounts_url(contract_id))
        # The dashboard endpoint wraps the list under {"data": [...]}.
        if isinstance(body, dict) and "data" in body:
            items = body["data"]
        elif isinstance(body, list):
            items = body
        else:
            raise ApiError(
                f"Unexpected /dashboard/.../accounts shape: {type(body).__name__}",
                status_code=200,
                body=body,
            )
        if not isinstance(items, list):
            raise ApiError(
                "/dashboard/.../accounts items field is not a list.",
                status_code=200,
                body=items,
            )
        return [Account.model_validate(item) for item in items]

    def list_with_dashboard(self, contract_id: str) -> _AccountList:
        """Merge legacy balances with the dashboard's full account list.

        Best of both worlds: gets the complete 5-account list (including
        Smart Cash USD) AND attaches the ``position`` / ``plus_minus``
        balance fields where the legacy endpoint provides them. For
        accounts that only show up on the dashboard endpoint (Smart Cash
        USD), the balance fields stay ``None``.
        """
        dashboard = self.list_dashboard(contract_id)
        try:
            legacy = {a.account_id: a for a in self.list(contract_id)}
        except ApiError:
            legacy = {}
        merged: _AccountList = []
        for d in dashboard:
            leg = legacy.get(d.account_id)
            if leg is None:
                merged.append(d)
                continue
            # Take the dashboard entry as canonical (so is_smart_cash_usd
            # is preserved) and overlay the balance fields from legacy.
            merged.append(
                d.model_copy(
                    update={
                        "position": leg.position,
                        "plus_minus": leg.plus_minus,
                        "plus_minus_percentage": leg.plus_minus_percentage,
                        "profile_type": leg.profile_type or d.profile_type,
                    }
                )
            )
        return merged

    def get_trading(self, contract_id: str) -> Account:
        """First active ``trading`` (BMV) account, raising if none.

        Useful because ``Portfolio.md`` tracks only the BMV trading
        strategy. Add equivalents for ``trading_usa`` etc. if needed.
        """
        for acct in self.list(contract_id):
            if acct.management_type_template == AccountType.TRADING and acct.status == "active":
                return acct
        raise ApiError("No active 'trading' account found.", status_code=200)
