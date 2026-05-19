"""Tests for the Markdown writer used by ``gbm-mx sync``."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from gbm_mx_api.cli._portfolio_md import (
    HEADER_ROW,
    append_rows,
    existing_ids,
    format_date,
    format_money,
    format_time,
    render_new_rows,
    render_row,
)
from gbm_mx_api.domain import FilledOrder, InstrumentType, Side

UTC_MINUS_6 = timezone.utc.utcoffset(None)  # not used directly; using offsets below


def _make_order(
    *,
    sob_id: int = 109142599,
    issue_id: str = "WDC *",
    side: Side = Side.BUY,
    qty: int = 1,
    price: str = "8692.24",
    commission: str = "21.73",
    when: datetime | None = None,
) -> FilledOrder:
    when = when or datetime(2026, 5, 14, 8, 30, 49)
    return FilledOrder(
        sob_id=sob_id,
        account_id="EP47NC05",
        issue_id=issue_id,
        instrument_type=InstrumentType.SIC,
        side=side,
        quantity=qty,
        average_price=Decimal(price),
        commission=Decimal(commission),
        iva=Decimal("3.48"),
        processed_at=when,
    )


# ----------------------------------------------------------------------
# Formatters
# ----------------------------------------------------------------------
def test_format_date_spanish_lowercase() -> None:
    from datetime import date

    assert format_date(date(2026, 5, 14)) == "14 mayo 2026"
    assert format_date(date(2026, 1, 7)) == "07 enero 2026"


def test_format_time_uses_12h_with_periods() -> None:
    assert format_time(datetime(2026, 5, 14, 8, 30)) == "08:30 a.m."
    assert format_time(datetime(2026, 5, 14, 13, 5)) == "01:05 p.m."
    assert format_time(datetime(2026, 5, 14, 0, 0)) == "12:00 a.m."
    assert format_time(datetime(2026, 5, 14, 12, 0)) == "12:00 p.m."


def test_format_money_with_thousands_and_dollar() -> None:
    assert format_money(Decimal("8692.24")) == "$8,692.24 MXN"
    assert format_money(Decimal("21.73"), include_dollar=False) == "21.73 MXN"
    assert format_money(Decimal("0.07"), include_dollar=False) == "0.07 MXN"


# ----------------------------------------------------------------------
# render_row — matches the existing Portfolio.md style exactly
# ----------------------------------------------------------------------
def test_render_row_buy_matches_expected_format() -> None:
    order = _make_order()
    row = render_row(order)
    expected = (
        "| 14 mayo 2026 | 08:30 a.m. | WDC * | Compra | 1 | "
        "$8,692.24 MXN | $8,692.24 MXN | 0.25% | 21.73 MXN | Llena | "
        "109142599 | EP47NC05 |"
    )
    assert row == expected


def test_render_row_sell_uses_venta() -> None:
    order = _make_order(side=Side.SELL)
    assert " Venta " in render_row(order)


# ----------------------------------------------------------------------
# existing_ids — parses the markdown table back
# ----------------------------------------------------------------------
def test_existing_ids_extracts_from_real_table(tmp_path: Path) -> None:
    md = tmp_path / "Portfolio.md"
    md.write_text(
        HEADER_ROW + "\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 14 mayo 2026 | 08:30 a.m. | WDC * | Compra | 1 | $8,692.24 MXN | "
        "$8,692.24 MXN | 0.25% | 21.73 MXN | Llena | 109142599 | EP47NC05 |\n"
        "| 14 mayo 2026 | 08:25 a.m. | FMTY 14 | Compra | 1 | $14.66 MXN | "
        "$14.66 MXN | 0.25% | 0.03 MXN | Llena | 109141831 | EP47NC05 |\n",
        encoding="utf-8",
    )
    assert existing_ids(md) == {109142599, 109141831}


def test_existing_ids_returns_empty_when_missing(tmp_path: Path) -> None:
    assert existing_ids(tmp_path / "nope.md") == set()


# ----------------------------------------------------------------------
# render_new_rows + dedup
# ----------------------------------------------------------------------
def test_render_new_rows_skips_existing_ids() -> None:
    o1 = _make_order(sob_id=1)
    o2 = _make_order(sob_id=2, issue_id="FMTY 14")
    o3 = _make_order(sob_id=3, issue_id="GAP B")
    rows = render_new_rows([o1, o2, o3], skip_ids={2})
    assert len(rows) == 2
    assert "FMTY 14" not in "\n".join(rows)


# ----------------------------------------------------------------------
# append_rows — file IO
# ----------------------------------------------------------------------
def test_append_rows_creates_file_with_header(tmp_path: Path) -> None:
    md = tmp_path / "Portfolio.md"
    append_rows(md, [render_row(_make_order())])
    text = md.read_text(encoding="utf-8")
    assert "# GBM Portfolio" in text
    assert HEADER_ROW in text
    assert "WDC *" in text


def test_append_rows_extends_existing_file(tmp_path: Path) -> None:
    md = tmp_path / "Portfolio.md"
    md.write_text(
        f"# Foo\n\n{HEADER_ROW}\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| 01 abril 2026 | 09:00 a.m. | XXX * | Compra | 1 | $1.00 MXN | "
        "$1.00 MXN | 0.25% | 0.00 MXN | Llena | 100000001 | EP47NC05 |\n",
        encoding="utf-8",
    )
    append_rows(md, [render_row(_make_order())])
    lines = md.read_text(encoding="utf-8").splitlines()
    assert lines[-2].endswith("100000001 | EP47NC05 |")
    assert lines[-1].endswith("109142599 | EP47NC05 |")
