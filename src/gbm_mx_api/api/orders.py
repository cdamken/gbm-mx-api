"""``/GBMP/api/Operation/GetBlotterOrders`` — order blotter (per-day query).

The backend's blotter endpoint only returns orders for a single day —
``processDate`` is mandatory in practice (no value → defaults to today;
``fromDate``/``toDate`` are silently ignored). To query a range, the
``list_filled`` helper iterates day by day.
"""

from __future__ import annotations

import datetime as _dt
import time
from collections.abc import Iterator

from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.enums import InstrumentType
from gbm_mx_api.domain.order import FilledOrder, Order
from gbm_mx_api.errors import ApiError

BLOTTER_URL = "https://homebroker-api.gbm.com/GBMP/api/Operation/GetBlotterOrders"

# Iteration is safe but polite: a few-second pause every N requests avoids
# hammering the backend when scanning months of history.
_PAUSE_EVERY = 10
_PAUSE_SECONDS = 0.5


def _process_date(d: _dt.date) -> str:
    """Format a date as the timestamp the backend expects.

    GBM treats the day boundary at 06:00 UTC (midnight Mexico City). The
    payload format is ISO 8601 ending with ``Z``.
    """
    return (
        _dt.datetime(d.year, d.month, d.day, 6, 0, 0, tzinfo=_dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _daterange(start: _dt.date, end: _dt.date) -> Iterator[_dt.date]:
    """Yield every date from ``start`` to ``end`` inclusive."""
    current = start
    one_day = _dt.timedelta(days=1)
    while current <= end:
        yield current
        current += one_day


class Orders(ApiBase):
    """Blotter (order book) endpoints."""

    DEFAULT_INSTRUMENT_TYPES: tuple[InstrumentType, ...] = (
        InstrumentType.BMV,
        InstrumentType.SIC,
    )

    def list_for_day(
        self,
        legacy_account_id: str,
        day: _dt.date,
        *,
        instrument_types: tuple[InstrumentType, ...] | None = None,
    ) -> list[Order]:
        """Raw orders (all statuses) submitted on ``day``.

        Note:
            This endpoint only returns orders for the **primary** trading
            account of a contract (e.g. ``EP47NC05``). Querying a secondary
            account (``EP47NC02`` Asesor, ``EP47NC03`` Trading USA) returns
            an empty list — passing the account UUID does NOT help (backend
            ignores it). Movements for those accounts live on
            ``api.appgbm.com/v2/.../transactions`` (see :mod:`gbm_mx_api.api.transactions`).
        """
        types = instrument_types or self.DEFAULT_INSTRUMENT_TYPES
        body = self._http.post(
            BLOTTER_URL,
            json={
                "contractId": legacy_account_id,
                "instrumentTypes": [int(t) for t in types],
                "processDate": _process_date(day),
            },
        )
        if not isinstance(body, dict):
            raise ApiError(
                f"Unexpected GetBlotterOrders shape: {type(body).__name__}",
                status_code=200,
                body=body,
            )
        raw_orders = body.get("ordersList") or []
        if not isinstance(raw_orders, list):
            raise ApiError(
                "GetBlotterOrders.ordersList is not a list.",
                status_code=200,
                body=raw_orders,
            )
        return [Order.model_validate(item) for item in raw_orders]

    def list_for_range(
        self,
        legacy_account_id: str,
        from_date: _dt.date,
        to_date: _dt.date,
        *,
        instrument_types: tuple[InstrumentType, ...] | None = None,
    ) -> list[Order]:
        """Raw orders (any status) submitted in ``[from_date, to_date]``.

        Iterates per-day because the backend's ``GetBlotterOrders`` only
        accepts one ``processDate`` at a time. De-duplicates by ``sob_id``.

        Args:
            legacy_account_id: e.g. ``"EP47NC05"``. Must be the primary
                trading account — see :meth:`list_for_day` note.
            from_date: First day, inclusive.
            to_date: Last day, inclusive.
            instrument_types: Defaults to BMV + SIC.
        """
        if from_date > to_date:
            raise ValueError("from_date must be <= to_date")

        seen_ids: set[int] = set()
        results: list[Order] = []
        days_done = 0

        for day in _daterange(from_date, to_date):
            # Let ApiError propagate — the caller can decide whether to
            # retry the whole range or skip the day.
            day_orders = self.list_for_day(
                legacy_account_id, day, instrument_types=instrument_types
            )
            for order in day_orders:
                if order.sob_id in seen_ids:
                    continue
                seen_ids.add(order.sob_id)
                results.append(order)

            days_done += 1
            if days_done % _PAUSE_EVERY == 0:
                time.sleep(_PAUSE_SECONDS)

        results.sort(key=lambda o: (o.process_date, o.sob_id))
        return results

    def list_filled(
        self,
        legacy_account_id: str,
        from_date: _dt.date,
        to_date: _dt.date,
        *,
        instrument_types: tuple[InstrumentType, ...] | None = None,
    ) -> list[FilledOrder]:
        """Every filled order in the range ``[from_date, to_date]``.

        Iterates per-day because the backend doesn't honor date ranges.
        Results are returned chronologically, deduplicated by ``sob_id``
        (defensive — duplicates should not happen but cost nothing to guard).

        Args:
            legacy_account_id: e.g. ``"EP47NC05"``. Primary trading account
                only — see :meth:`list_for_day` note.
            from_date: First day, inclusive.
            to_date: Last day, inclusive.
            instrument_types: Defaults to BMV + SIC.
        """
        if from_date > to_date:
            raise ValueError("from_date must be <= to_date")

        seen_ids: set[int] = set()
        results: list[FilledOrder] = []
        days_done = 0

        for day in _daterange(from_date, to_date):
            # Let ApiError propagate — the caller can decide whether to
            # retry the whole range or skip the day.
            day_orders = self.list_for_day(
                legacy_account_id, day, instrument_types=instrument_types
            )
            for order in day_orders:
                if not order.is_filled:
                    continue
                if order.sob_id in seen_ids:
                    continue
                seen_ids.add(order.sob_id)
                results.append(order.to_filled())

            days_done += 1
            if days_done % _PAUSE_EVERY == 0:
                time.sleep(_PAUSE_SECONDS)

        results.sort(key=lambda o: (o.processed_at, o.sob_id))
        return results
