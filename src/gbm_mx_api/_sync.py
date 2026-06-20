"""Shared fetch orchestration — the data núcleo for the GBM trio.

This module owns the *business logic* that both downstream fetchers used to
copy-paste: session refresh, the contracts→accounts→positions→orders→
dividends→transactions pipeline, the incremental/full window, fx.json, and
the JSON writers. It is written ONCE here and imported by:

  * gbm-dashboard/app/fetch_data.py        (local single-user)
  * gbm-owncloud/python/fetch_wrapper.py   (multi-user ownCloud port)

Each of those is now a thin *host adapter*: it resolves paths/credentials,
maps exceptions to process exit codes, picks an interactive vs fixed TOTP
provider, and then calls :func:`sync`. Everything host-agnostic lives here so
a fix (TOTP refresh, Trading USA orders, the backfill window, fx.json) is a
single edit instead of two.

The module is named ``_sync`` (not ``sync``) so the public ``sync`` function
exported at the package root doesn't collide with / shadow a same-named
submodule. Import it as ``from gbm_mx_api import sync``.

See ADR ``2026-06-16 — ALL — Núcleo compartido`` in
Portfolio-Master/DECISIONS.md and gbm-mx-api issue #2.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from gbm_mx_api.auth.session import DEFAULT_SESSION_PATH, Session
from gbm_mx_api.client import GbmClient
from gbm_mx_api.errors import ApiError, AuthError, TransportError

# Buffer in days for the incremental window: we re-fetch this many days BEFORE
# the last_update timestamp so late settlements (T+2 trades, dividends posted a
# few days after the ex-date, etc.) get picked up and merged. The merge dedupes
# by unique id, so the overlap is harmless.
INCREMENTAL_BUFFER_DAYS = 14

# All 5 investment sections used by GBM's GetPositionSummary.
INVEST_SECTIONS = (
    "mercados_globales_sic",
    "mercado_capitales",
    "sociedades_inversion_deuda",
    "sociedades_inversion_comun",
    "mercado_extranjero",
)

Logger = Callable[[str], None]


# ---------------------------------------------------------------------------
# Session — proactive refresh
# ---------------------------------------------------------------------------
def try_refresh_saved(session_path: Path = DEFAULT_SESSION_PATH) -> GbmClient | None:
    """Return a usable client from the saved session, or None if MFA is needed.

    GBM's access-token TTL is far shorter than the 3600s we store, and it can
    be revoked early (e.g. when you log into the GBM app on your phone), so it
    401s a token we still consider "valid" by the local clock. ``from_saved()``
    only refreshes when ``is_expired`` is True, so that case slips through →
    401 → wipe → re-TOTP loop. Fix: on every run, proactively mint a fresh
    access token from the long-lived ``refresh_token`` (Cognito refresh tokens
    last ~days). Only fall back to MFA if the refresh token itself is revoked.

    Returns None when there is no saved session, or it has no refresh token and
    its access token is expired — the caller decides whether to prompt for a
    TOTP (interactive) or exit with an MFA-required code (non-interactive).
    """
    from gbm_mx_api.auth.refresh import refresh_session

    sess = Session.try_load(session_path)
    if sess is not None and sess.refresh_token:
        try:
            sess = refresh_session(sess)
            with contextlib.suppress(OSError):
                sess.save(session_path)
            return GbmClient.from_session(sess)
        except (AuthError, ApiError, TransportError):
            pass  # refresh token revoked / Cognito down → need fresh MFA
    if sess is not None and not sess.is_expired:
        # No refresh token but the access token still looks valid — use it.
        return GbmClient.from_session(sess)
    return None


def fetch_usdmxn_rate() -> float | None:
    """Latest USD/MXN spot (pesos per 1 USD) from Yahoo, or None.

    GBM reports Trading USA in pesos with no FX field, so we fetch a live rate
    to show the USD equivalent. Server-side (no CORS); best-effort.
    """
    import urllib.error
    import urllib.request

    url = "https://query1.finance.yahoo.com/v8/finance/chart/MXN=X?interval=1d&range=5d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            payload = json.loads(r.read())
        result = (payload.get("chart") or {}).get("result") or [{}]
        quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
        closes = [c for c in (quote.get("close") or []) if c]
        return round(float(closes[-1]), 4) if closes else None
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ValueError,
        KeyError,
        IndexError,
    ):
        return None


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def write_json(path: Path, data: Any, *, secure: bool = False, log: Logger = print) -> None:
    """Atomically write JSON: tmp → fsync → rename.

    Without the atomic dance, killing the process mid-write (Ctrl-C, kill, OOM)
    leaves a truncated file and the UI shows "Sin datos" until the next
    successful update. ``secure=True`` also chmods the file to 0600 (ownCloud
    per-user data dirs).
    """
    payload = to_jsonable(data)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    if secure:
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
    size_kb = path.stat().st_size / 1024
    log(f"  wrote {path.name} ({size_kb:.1f} KB)")


def read_last_update_date(data_dir: Path) -> date | None:
    """Return the date portion of {data_dir}/last_update.date, or None.

    None triggers a full-window fetch. Accepts both the legacy
    ``2026-06-10 09:21:43`` (naive) and current ``2026-06-10T09:21:43Z`` (UTC
    ISO 8601) formats — only the YYYY-MM-DD prefix matters for the window.
    """
    path = data_dir / "last_update.date"
    if not path.exists():
        return None
    try:
        first_line = path.read_text(encoding="utf-8").strip().splitlines()[0]
        date_part = first_line.split("T")[0].split()[0]
        return date.fromisoformat(date_part)
    except (OSError, ValueError, IndexError):
        return None


def account_start_date(
    client: GbmClient,
    contract: Any,
    accounts: list[Any],
    out_dir: Path,
    *,
    log: Logger = print,
) -> date | None:
    """Earliest transaction date across all accounts = the account-open date.

    Why this exists: ``GetBlotterOrders`` is queried DAY BY DAY, so a full
    orders backfill costs one HTTP call per day in the window *regardless of
    whether that day has any orders*. A fixed window is wrong both ways — too
    short truncates real history, too long fires thousands of empty-day calls
    (10 years x several accounts) and blows the subprocess timeout. Instead we
    bound the backfill to the account's FIRST real movement: transactions DO
    honor a date range (paginated, not day-by-day), so one cheap range query
    per account reveals the earliest ``process_date``.

    The result is cached in ``{out_dir}/account_start.date`` so we discover it
    once — a later full reload (or a reset) reuses it instead of re-scanning,
    and a UI that lets the user state when they opened the account can seed
    this file directly.

    Returns None if no transactions are found (brand-new account or all calls
    failed); the caller then falls back to its safety-cap window.
    """
    cache = out_dir / "account_start.date"
    if cache.exists():
        try:
            cached = date.fromisoformat(cache.read_text(encoding="utf-8").strip()[:10])
            log(f"  account start: {cached} (cached)")
            return cached
        except (OSError, ValueError):
            pass  # unreadable cache → rediscover

    # Look back a generously wide window only to FIND the floor; the range
    # query is cheap (server-side pagination), unlike the day-by-day orders.
    cap_days = int(os.environ.get("GBM_ORDERS_DAYS", "3650"))
    wide_from = date.today() - timedelta(days=cap_days)
    earliest: date | None = None
    for acct in accounts:
        try:
            txs = client.transactions.list_for_range(
                contract.contract_id, acct.legacy_contract_id, wide_from, date.today()
            )
        except (ApiError, TransportError) as e:
            log(f"  account start probe {acct.name}: skipped ({type(e).__name__})")
            continue
        for t in txs:
            pd = t.process_date
            d = pd.date() if isinstance(pd, datetime) else pd
            if isinstance(d, date) and (earliest is None or d < earliest):
                earliest = d

    if earliest is not None:
        with contextlib.suppress(OSError):
            cache.write_text(earliest.isoformat() + "\n", encoding="utf-8")
        log(f"  account start: {earliest} (discovered from transactions)")
    else:
        log("  account start: none found (no transactions) — using safety cap")
    return earliest


def merge_records(
    existing_path: Path,
    new_payload: dict[str, Any],
    list_field: str,
    key_fn: Callable[[Any], Any],
    sort_key: str,
    sort_reverse: bool = True,
) -> dict[str, Any]:
    """Merge ``new_payload[list_field]`` into the existing JSON at path.

    On key collision the NEW record wins (so server-side corrections propagate
    — e.g. a pending order flipping to filled). Existing records absent from
    this fetch are kept (older than the incremental cutoff). The older
    ``from_date`` is preserved so the JSON metadata reflects the full window.

    Mutates ``new_payload[list_field]`` in place and returns ``new_payload``.
    """
    existing_records: list[Any] = []
    existing_from: str | None = None
    if existing_path.exists():
        try:
            with existing_path.open(encoding="utf-8") as f:
                existing = json.load(f)
            existing_records = existing.get(list_field, []) or []
            existing_from = existing.get("from_date")
        except (json.JSONDecodeError, OSError):
            pass  # treat as fresh fetch

    by_key: dict[Any, Any] = {}
    # Existing first so new records take precedence on collision.
    for r in existing_records:
        try:
            by_key[key_fn(r)] = r
        except (KeyError, TypeError):
            continue
    for r in new_payload.get(list_field, []) or []:
        try:
            by_key[key_fn(r)] = r
        except (KeyError, TypeError):
            continue
    merged = list(by_key.values())
    merged.sort(key=lambda r: r.get(sort_key, "") or "", reverse=sort_reverse)
    new_payload[list_field] = merged

    new_from = new_payload.get("from_date")
    if existing_from and (not new_from or existing_from < new_from):
        new_payload["from_date"] = existing_from
    return new_payload


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------
def sync(
    client: GbmClient,
    out_dir: Path,
    *,
    full: bool = False,
    email: str | None = None,
    secure: bool = False,
    log: Logger = print,
) -> None:
    """Fetch the full GBM dataset for ``client`` and write JSON into ``out_dir``.

    Writes accounts.json, investments_groups.json, positions.json, fx.json,
    orders.json, orders_all.json, dividends.json, transactions.json and
    last_update.date.

    Args:
        client: an authenticated :class:`GbmClient` (caller handles auth).
        out_dir: directory to write the JSON files into (created if missing).
        full: force a full-window fetch instead of incremental merge. Used on
            first run, after a reset, or when the user asks to reload from
            scratch. Without it the existing ``last_update.date`` drives an
            incremental window that merges by unique id.
        email: GBM account email, used for the investments-groups endpoint
            (the "TOTAL INVERTIDO" source). Skipped if falsy.
        secure: chmod 0600/0700 the written files and dir (ownCloud per-user).
        log: progress sink (defaults to print).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if secure:
        with contextlib.suppress(OSError):
            os.chmod(out_dir, 0o700)

    # Decide incremental vs full BEFORE any API call so we know which date
    # range to ask for and whether to merge or overwrite.
    last_update = read_last_update_date(out_dir)
    incremental = last_update is not None and not full
    if incremental:
        assert last_update is not None  # guaranteed by `incremental`; narrows for mypy
        incremental_from = last_update - timedelta(days=INCREMENTAL_BUFFER_DAYS)
        log(
            f"Incremental mode — fetching since {incremental_from} "
            f"(last_update = {last_update}, buffer = {INCREMENTAL_BUFFER_DAYS}d)"
        )
    else:
        # Unused in full mode; the assignment keeps the type a definite `date`
        # (not date | None) so the window math below stays well-typed.
        incremental_from = date.today()
        reason = "forced via --full" if full else "first run / no last_update.date"
        log(f"Full mode ({reason}) — pulling the configured days window.")

    contract = client.contracts.get_main()
    log(f"  contract: {contract.legacy_contract_id}")

    # list_with_dashboard merges the legacy /v2 endpoint (balances) with the
    # newer appgbm.com /dashboard endpoint (which includes the otherwise-hidden
    # Smart Cash Dólares account).
    accounts = client.accounts.list_with_dashboard(contract.contract_id)
    log(f"  accounts: {len(accounts)}")

    # The v3/dashboard/investments-groups endpoint is what the GBM mobile app
    # uses to compute "TOTAL INVERTIDO". Its FX rate matches the mobile app
    # exactly, so we save it as the authoritative source for the total card.
    if email:
        try:
            ig = client.dashboard.investments_groups(contract.contract_id, email)
            write_json(
                out_dir / "investments_groups.json",
                ig.model_dump(by_alias=False),
                secure=secure,
                log=log,
            )
            log(
                f"  investments-groups: total=${float(ig.total_position.amount):,.2f} "
                f"({len(ig.groups)} groups)"
            )
        except (ApiError, TransportError) as e:
            # This endpoint times out frequently (it joins live FX, homebroker,
            # and offshore data server-side). Treat a timeout as non-fatal —
            # the UI falls back to the per-account sum which is close enough.
            log(f"  investments-groups: SKIPPED ({type(e).__name__}: {e})")
    else:
        log("  investments-groups: skipped (no GBM_EMAIL in env)")

    accounts_payload = [
        {
            "legacy_contract_id": a.legacy_contract_id,
            "account_id": a.account_id,
            "name": a.name,
            "number": a.number,
            "management_type_template": a.management_type_template,
            "position": {
                "amount": float(a.position.amount) if a.position else None,
                "currency": a.position.currency if a.position else None,
            },
            "plus_minus": {
                "amount": float(a.plus_minus.amount) if a.plus_minus else None,
                "currency": a.plus_minus.currency if a.plus_minus else None,
            },
            "plus_minus_percentage": a.plus_minus_percentage,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in accounts
    ]
    write_json(out_dir / "accounts.json", accounts_payload, secure=secure, log=log)

    positions_by_account: dict[str, Any] = {}
    for a in accounts:
        try:
            # Pass account_id (UUID) so non-primary accounts (Asesor, Trading
            # USA) also return their full holdings.
            summary = client.positions.summary(a.legacy_contract_id, account_id=a.account_id)
            positions_by_account[a.legacy_contract_id] = to_jsonable(
                summary.model_dump(by_alias=False)
            )
            count = sum(
                1
                for section_key in INVEST_SECTIONS
                for p in positions_by_account[a.legacy_contract_id].get(section_key) or []
                if p.get("issue_id") != "Subtotal"
            )
            log(f"  positions for {a.legacy_contract_id} ({a.name}): {count}")
        except ApiError as e:
            log(f"  positions for {a.legacy_contract_id} ({a.name}): {e}")
            positions_by_account[a.legacy_contract_id] = None

    write_json(out_dir / "positions.json", positions_by_account, secure=secure, log=log)

    # USD/MXN rate so the UI can show Trading USA values (GBM reports them in
    # pesos) alongside their USD equivalent. Non-fatal: a missing rate just
    # hides the "(≈ $USD)" hint.
    rate = fetch_usdmxn_rate()
    if rate:
        write_json(
            out_dir / "fx.json",
            {
                "usdmxn": rate,
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            secure=secure,
            log=log,
        )

    # ----------------------------------------------------------------------
    # Orders for EVERY trading account, all statuses. One backend call per
    # account (list_for_range returns any status); we derive two JSON files
    # from the same data so the UI never has to query twice:
    #   orders.json     — only filled  (Movimientos page)
    #   orders_all.json — every status (Histórico page)
    #
    # Include Trading USA (template "trading_usa") alongside the Mexican
    # "trading" accounts — its orders come from the same GetBlotterOrders
    # endpoint. The "== 'trading'" filter silently dropped Trading USA, so USA
    # buys/sells (e.g. a partial sell) never showed in Movimientos even though
    # MX ones did. The per-account call is wrapped in try/except, so if GBM
    # rejects the USA account it's logged and skipped rather than fatal.
    # ----------------------------------------------------------------------
    trading_accounts = [
        a for a in accounts if a.management_type_template in ("trading", "trading_usa")
    ]
    if trading_accounts:
        to_date_ = date.today()
        if incremental:
            from_date_ = incremental_from
        else:
            # Full backfill. GetBlotterOrders is queried DAY BY DAY (one call
            # per day per account), so the window length = number of sequential
            # HTTP calls. A fixed window is wrong both ways: too short truncates
            # real history, too long fires thousands of empty pre-account-open
            # calls and blows the subprocess timeout. So bound it to the
            # account's first real movement (earliest transaction), cached in
            # account_start.date. GBM_ORDERS_DAYS is now only a safety CAP for
            # the rare case no transactions are found.
            cap_days = int(os.environ.get("GBM_ORDERS_DAYS", "3650"))
            floor = to_date_ - timedelta(days=cap_days)
            start = account_start_date(client, contract, accounts, out_dir, log=log)
            from_date_ = max(start, floor) if start is not None else floor
        log(
            f"  fetching orders {from_date_} → {to_date_} "
            f"for {len(trading_accounts)} trading account(s)..."
        )

        all_orders: list[dict[str, Any]] = []
        filled_orders: list[dict[str, Any]] = []
        for acct in trading_accounts:
            try:
                raw_orders = client.orders.list_for_range(
                    acct.legacy_contract_id, from_date_, to_date_
                )
            except ApiError as e:
                log(f"  {acct.name} ({acct.legacy_contract_id}): {e}")
                continue
            n_filled = sum(1 for o in raw_orders if o.is_filled)
            log(
                f"  {acct.name} ({acct.legacy_contract_id}): "
                f"{len(raw_orders)} total, {n_filled} filled"
            )
            for o in raw_orders:
                amount = float(o.assigned_quantity * o.average_price)
                common = {
                    "sob_id": o.sob_id,
                    "account_id": o.account_id,
                    "issue_id": o.issue_id,
                    "instrument_type": int(o.instrument_type),
                    "side": o.side.name,
                    "status": o.status,
                    "status_label": o.status_label,
                    "is_filled": o.is_filled,
                    "is_cancelled": o.is_cancelled,
                    "original_quantity": o.original_quantity,
                    "assigned_quantity": o.assigned_quantity,
                    "cancel_quantity": o.cancel_quantity,
                    "quantity": o.assigned_quantity if o.is_filled else o.original_quantity,
                    "average_price": float(o.average_price),
                    "limit_price": float(o.price),
                    "amount": amount,
                    "commission": float(o.commission),
                    "iva": float(o.iva),
                    "processed_at": o.process_date.isoformat(),
                    "cancel_message": o.cancel_message,
                    "account_legacy_id": acct.legacy_contract_id,
                    "account_name": acct.name,
                }
                all_orders.append(common)
                if o.is_filled:
                    filled_orders.append(common)

        all_orders.sort(key=lambda o: o["processed_at"])
        filled_orders.sort(key=lambda o: o["processed_at"])

        accounts_meta = [
            {"legacy_contract_id": a.legacy_contract_id, "name": a.name} for a in trading_accounts
        ]
        filled_payload = {
            "from_date": from_date_.isoformat(),
            "to_date": to_date_.isoformat(),
            "accounts": accounts_meta,
            "orders": filled_orders,
        }
        all_payload = {
            "from_date": from_date_.isoformat(),
            "to_date": to_date_.isoformat(),
            "accounts": accounts_meta,
            "orders": all_orders,
        }
        if incremental:
            # Merge by sob_id (9-digit unique order id). A pending order from a
            # previous run can flip to filled — the new record wins on collision.
            filled_payload = merge_records(
                out_dir / "orders.json",
                filled_payload,
                list_field="orders",
                key_fn=lambda r: r.get("sob_id"),
                sort_key="processed_at",
            )
            all_payload = merge_records(
                out_dir / "orders_all.json",
                all_payload,
                list_field="orders",
                key_fn=lambda r: r.get("sob_id"),
                sort_key="processed_at",
            )
        write_json(out_dir / "orders.json", filled_payload, secure=secure, log=log)
        write_json(out_dir / "orders_all.json", all_payload, secure=secure, log=log)
    else:
        log("  no trading accounts → skipping orders download.")

    # ----------------------------------------------------------------------
    # Dividends — cash distributions via api.appgbm.com. Paginates server-side;
    # we iterate every trading account so multi-contract users see them all.
    # ----------------------------------------------------------------------
    if trading_accounts:
        div_to = date.today()
        if incremental:
            div_from = incremental_from
        else:
            div_days_back = int(os.environ.get("GBM_DIVIDENDS_DAYS", "3650"))
            div_from = div_to - timedelta(days=div_days_back)
        log(
            f"  fetching dividends {div_from} → {div_to} "
            f"for {len(trading_accounts)} trading account(s)..."
        )
        dividends_payload: list[dict[str, Any]] = []
        for acct in trading_accounts:
            try:
                divs = client.dividends.list_for_range(
                    contract.contract_id,
                    acct.legacy_contract_id,
                    div_from,
                    div_to,
                )
            except ApiError as e:
                # api.appgbm.com may reject our token (different Cognito client)
                # — log and skip rather than fail the whole run.
                log(f"  dividends {acct.name} ({acct.legacy_contract_id}): {e}")
                continue
            log(f"  dividends {acct.name} ({acct.legacy_contract_id}): {len(divs)} item(s)")
            for d in divs:
                dividends_payload.append(
                    {
                        "transaction_id": d.transaction_id,
                        "security_id": d.security_id,
                        "security_name": d.security_name,
                        "description": d.transaction_description,
                        "amount": float(d.transaction_amount),
                        "net_amount": float(d.transaction_net_amount),
                        "is_withholding": d.is_withholding,
                        "process_date": d.process_date.isoformat(),
                        "settlement_date": (
                            d.settlement_date.isoformat() if d.settlement_date else None
                        ),
                        "transaction_time": d.transaction_time,
                        "account_legacy_id": acct.legacy_contract_id,
                        "account_name": acct.name,
                    }
                )
        dividends_payload.sort(key=lambda d: d["process_date"], reverse=True)
        div_file_payload = {
            "from_date": div_from.isoformat(),
            "to_date": div_to.isoformat(),
            "dividends": dividends_payload,
        }
        if incremental:
            div_file_payload = merge_records(
                out_dir / "dividends.json",
                div_file_payload,
                list_field="dividends",
                key_fn=lambda r: r.get("transaction_id"),
                sort_key="process_date",
            )
        write_json(out_dir / "dividends.json", div_file_payload, secure=secure, log=log)

    # ----------------------------------------------------------------------
    # Transactions (full ledger). Same endpoint as dividends but with no
    # transac_type filter so we get EVERY movement: stock/fund buys & sells,
    # repos, cash transfers, FX, dividends. Iterated over ALL accounts (not
    # just trading) so Smart Cash, Asesor and Trading USA are covered.
    # ----------------------------------------------------------------------
    if accounts:
        tx_to = date.today()
        if incremental:
            tx_from = incremental_from
        else:
            tx_days_back = int(os.environ.get("GBM_TRANSACTIONS_DAYS", "3650"))
            tx_from = tx_to - timedelta(days=tx_days_back)
        log(f"  fetching transactions {tx_from} → {tx_to} for {len(accounts)} account(s)...")
        transactions_payload: list[dict[str, Any]] = []
        for acct in accounts:
            try:
                txs = client.transactions.list_for_range(
                    contract.contract_id,
                    acct.legacy_contract_id,
                    tx_from,
                    tx_to,
                )
            except ApiError as e:
                log(f"  transactions {acct.name} ({acct.legacy_contract_id}): {e}")
                continue
            log(f"  transactions {acct.name} ({acct.legacy_contract_id}): {len(txs)} item(s)")
            for t in txs:
                transactions_payload.append(
                    {
                        "transaction_id": t.transaction_id,
                        "security_id": t.security_id,
                        "security_name": t.security_name,
                        "transaction_type": t.transaction_type,
                        "sub_transaction_type": t.sub_transaction_type,
                        "description": t.transaction_description,
                        "category": t.category,
                        "is_buy": t.is_buy,
                        "is_sell": t.is_sell,
                        "is_cash_flow": t.is_cash_flow,
                        "amount": float(t.transaction_amount),
                        "net_amount": float(t.transaction_net_amount),
                        "quantity": float(t.quantity),
                        "price": float(t.transaction_price),
                        "commission": float(t.transaction_commission),
                        "tax": float(t.transaction_tax),
                        "process_date": t.process_date.isoformat(),
                        "settlement_date": (
                            t.settlement_date.isoformat() if t.settlement_date else None
                        ),
                        "transaction_time": t.transaction_time,
                        "account_legacy_id": acct.legacy_contract_id,
                        "account_name": acct.name,
                    }
                )
        transactions_payload.sort(key=lambda t: t["process_date"], reverse=True)
        accounts_meta_all = [
            {"legacy_contract_id": a.legacy_contract_id, "name": a.name} for a in accounts
        ]
        tx_file_payload = {
            "from_date": tx_from.isoformat(),
            "to_date": tx_to.isoformat(),
            "accounts": accounts_meta_all,
            "transactions": transactions_payload,
        }
        if incremental:
            tx_file_payload = merge_records(
                out_dir / "transactions.json",
                tx_file_payload,
                list_field="transactions",
                key_fn=lambda r: r.get("transaction_id"),
                sort_key="process_date",
            )
        write_json(out_dir / "transactions.json", tx_file_payload, secure=secure, log=log)

    # ISO 8601 UTC with explicit Z — browser JS parses the `Z` and converts to
    # user-local via toLocaleTimeString(). Fixes the "Updated 07:21 AM" stale
    # chip on a UTC server.
    (out_dir / "last_update.date").write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ\n"),
        encoding="utf-8",
    )
