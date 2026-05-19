"""Markdown table writer for the user's ``Portfolio.md`` ledger.

Column conventions:

- Fecha:                ``DD mes YYYY`` (mes in lowercase Spanish).
- Hora:                 ``HH:MM a.m.`` / ``HH:MM p.m.`` with a literal space.
- Precio / Importe:     ``$X,XXX.XX MXN``.
- Monto de Comisión:    ``X.XX MXN`` (no dollar sign).
- Comisión %:           always ``0.25%`` (config of the account, not in API).
- Estatus:              ``Llena``.
- ID:                   numeric, 9 digits.
- Contrato:             e.g. ``EP47NC05``.
- Row ordering:         chronological ascending.
- Dedup key:            ``ID de la orden``.

This module renders and parses those rows so the CLI ``sync`` command can
append new orders without breaking downstream consumers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from gbm_mx_api.domain import FilledOrder, Side

SPANISH_MONTHS = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

HEADER_ROW = (
    "| Fecha | Hora | Emisora | Tipo de operación | Titulos | Precio | Importe |"
    " Comisión | Monto de Comisión | Estatus de la orden | ID de la orden | Contrato |"
)
SEPARATOR_ROW = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"

# Matches an existing data row and captures the ``ID de la orden`` column
# (second-to-last cell). Used for dedup.
_ID_COLUMN_RE = re.compile(r"\|\s*(\d{6,12})\s*\|\s*[A-Z0-9]+\s*\|\s*$")


def format_date(d: date) -> str:
    return f"{d.day:02d} {SPANISH_MONTHS[d.month]} {d.year}"


def format_time(dt: datetime) -> str:
    """Return ``HH:MM a.m.`` / ``HH:MM p.m.`` with a literal space."""
    hour = dt.hour % 12 or 12
    suffix = "a.m." if dt.hour < 12 else "p.m."
    return f"{hour:02d}:{dt.minute:02d} {suffix}"


def format_money(amount: Decimal, *, include_dollar: bool = True) -> str:
    # Quantize to 2 decimals; Decimal handles bankers rounding by default.
    q = amount.quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    abs_q = abs(q)
    # Thousands separator via :,
    formatted = f"{abs_q:,.2f}"
    prefix = "$" if include_dollar else ""
    return f"{sign}{prefix}{formatted} MXN"


def render_row(order: FilledOrder, *, commission_pct: str = "0.25%") -> str:
    """Render a single filled order as a Portfolio.md data row."""
    fecha = format_date(order.processed_at.date())
    hora = format_time(order.processed_at)
    operacion = "Compra" if order.side is Side.BUY else "Venta"
    precio = format_money(order.average_price)
    importe = format_money(order.amount)
    comision = format_money(order.commission, include_dollar=False)
    return (
        f"| {fecha} | {hora} | {order.issue_id} | {operacion} | {order.quantity} | "
        f"{precio} | {importe} | {commission_pct} | {comision} | Llena | "
        f"{order.sob_id} | {order.account_id} |"
    )


def existing_ids(path: Path) -> set[int]:
    """Return the set of order IDs already present in ``path``."""
    if not path.exists():
        return set()
    ids: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ID_COLUMN_RE.search(line.rstrip())
        if m:
            ids.add(int(m.group(1)))
    return ids


def render_new_rows(
    orders: Iterable[FilledOrder],
    *,
    skip_ids: set[int] | None = None,
    commission_pct: str = "0.25%",
) -> list[str]:
    """Render each order, skipping those whose ID is in ``skip_ids``."""
    skip = skip_ids or set()
    return [render_row(o, commission_pct=commission_pct) for o in orders if o.sob_id not in skip]


def append_rows(path: Path, rows: list[str]) -> None:
    """Append rendered rows to ``Portfolio.md``.

    If ``path`` doesn't exist, creates it with a heading + table header.
    Each row goes on its own line (newline terminated).
    """
    path = Path(path)
    body = path.read_text(encoding="utf-8") if path.exists() else _empty_table()
    if not body.endswith("\n"):
        body += "\n"
    body += "\n".join(rows) + "\n"
    path.write_text(body, encoding="utf-8")


def _empty_table() -> str:
    return f"# GBM Portfolio - Transaction History\n\n{HEADER_ROW}\n{SEPARATOR_ROW}\n"
