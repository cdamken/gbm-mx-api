"""``/v2/trading/contracts/{contract_id}/transactions`` — full ledger.

Generalized client for every transaction the backend has on the account:
stock orders, fund buys/sells, money-market activity, cash transfers, FX,
and dividend-style entries. This is the "see everything" sibling of
:mod:`gbm_mx_api.api.dividends` (which exists for the narrow dividend
case on the same endpoint).

The backend lives on ``api.appgbm.com`` — a different host from the rest
of the GBM API surface (``api.gbm.com``, ``homebroker-api.gbm.com``).

Pagination: default 10 items/page, max ~100. The library walks every page
transparently and returns a single chronological list.

``transac_type`` is **ignored** by the backend (every value except
``"dividend"`` returns the same full result), so this client does not
expose it. Use :class:`Dividends` if you only want dividend events.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.transaction import Transaction
from gbm_mx_api.errors import ApiError

BASE_URL = "https://api.appgbm.com/v2/trading/contracts"

_DEFAULT_PAGE_SIZE = 100
_MAX_PAGES = 200


class Transactions(ApiBase):
    """Full-ledger endpoint on appgbm.com."""

    def list_for_range(
        self,
        contract_id: str,
        legacy_contract_id: str,
        from_date: _dt.date,
        to_date: _dt.date,
        *,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> list[Transaction]:
        """Every transaction in ``[from_date, to_date]`` for one legacy account.

        Args:
            contract_id: UUID of the parent contract (NOT the legacy id).
            legacy_contract_id: Specific account legacy id — e.g. ``"EP47NC02"``
                for Asesor or ``"EP47NC01"`` for Smart Cash. Unlike
                ``GetBlotterOrders``, this endpoint **does** honor the
                per-account legacy id, so secondary accounts return their
                own movements.
            from_date: First day, inclusive.
            to_date: Last day, inclusive.
            page_size: Items per page (server default 10, max ~100).

        Returns:
            Transactions sorted by ``process_date`` ascending, deduplicated
            by ``transaction_id`` (defensive — paginated APIs can repeat).
        """
        if from_date > to_date:
            raise ValueError("from_date must be <= to_date")

        url = f"{BASE_URL}/{contract_id}/transactions"
        all_items: list[Transaction] = []
        seen_ids: set[int] = set()

        page = 1
        while page <= _MAX_PAGES:
            params: dict[str, Any] = {
                "page": page,
                "page_size": page_size,
                "start_date": from_date.isoformat(),
                "end_date": to_date.isoformat(),
                "legacy_contracts_id": legacy_contract_id,
            }
            body = self._http.get(url, params=params)
            if not isinstance(body, dict):
                raise ApiError(
                    f"Unexpected /transactions shape: {type(body).__name__}",
                    status_code=200,
                    body=body,
                )

            items = body.get("items") or []
            if not isinstance(items, list):
                raise ApiError(
                    "/transactions items field is not a list.",
                    status_code=200,
                    body=items,
                )
            # Defensive: if the backend keeps advertising "next" but stops
            # sending items, stop the loop instead of looping to _MAX_PAGES
            # asking for empty pages.
            if not items:
                break
            for raw in items:
                t = Transaction.model_validate(raw)
                if t.transaction_id in seen_ids:
                    continue
                seen_ids.add(t.transaction_id)
                all_items.append(t)

            meta = body.get("pagination_metadata") or {}
            if not meta.get("next"):
                break
            page += 1

        all_items.sort(key=lambda t: (t.process_date, t.transaction_id))
        return all_items
