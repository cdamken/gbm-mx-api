"""``/v2/trading/contracts/{contract_id}/transactions`` — dividends + cash flows.

This endpoint lives on a **different backend** (``api.appgbm.com``) from the
rest of the GBM API surface (``api.gbm.com``, ``homebroker-api.gbm.com``).
It's the data source used by the "Dividendos" tab on the basic
appgbm.com web app — *not* the gbmplus or trading homebroker UIs.

The endpoint paginates: 10 items per page by default. The library handles
pagination transparently — :meth:`Dividends.list_for_range` loops through
every page and returns a single chronological list.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.dividend import Dividend
from gbm_mx_api.errors import ApiError

# Different host from the rest of the API — discovered 2026-05 via DevTools.
BASE_URL = "https://api.appgbm.com/v2/trading/contracts"

# Server default is 10; we ask for 100 to minimize round-trips on long ranges.
_DEFAULT_PAGE_SIZE = 100
# Hard cap so a runaway loop never iterates forever.
_MAX_PAGES = 200


class Dividends(ApiBase):
    """Dividend / cash-distribution endpoints."""

    def list_for_range(
        self,
        contract_id: str,
        legacy_contract_id: str,
        from_date: _dt.date,
        to_date: _dt.date,
        *,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> list[Dividend]:
        """Every dividend-type movement in ``[from_date, to_date]``.

        Args:
            contract_id: UUID of the contract (NOT the legacy id).
            legacy_contract_id: e.g. ``"EP47NC05"``. Sent as a query param —
                the backend uses it for legacy joins.
            from_date: First day, inclusive.
            to_date: Last day, inclusive.
            page_size: Items per page (server default 10, max ~100).

        Returns:
            Dividend events sorted by ``process_date`` ascending. The list
            includes both gross payouts and the matching ISR withholding
            lines — caller can filter via :attr:`Dividend.is_withholding`.
        """
        if from_date > to_date:
            raise ValueError("from_date must be <= to_date")

        url = f"{BASE_URL}/{contract_id}/transactions"
        all_items: list[Dividend] = []
        seen_ids: set[int] = set()

        page = 1
        while page <= _MAX_PAGES:
            params: dict[str, Any] = {
                "page": page,
                "page_size": page_size,
                "start_date": from_date.isoformat(),
                "end_date": to_date.isoformat(),
                "transac_type": "dividend",
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
            # sending items, stop the loop. Otherwise we'd iterate up to
            # _MAX_PAGES requesting empty pages.
            if not items:
                break
            for raw in items:
                d = Dividend.model_validate(raw)
                # Defensive de-dupe (paginated APIs can repeat on edges).
                if d.transaction_id in seen_ids:
                    continue
                seen_ids.add(d.transaction_id)
                all_items.append(d)

            # Stop when the backend doesn't advertise a next page.
            meta = body.get("pagination_metadata") or {}
            if not meta.get("next"):
                break
            page += 1

        all_items.sort(key=lambda d: (d.process_date, d.transaction_id))
        return all_items
