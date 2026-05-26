"""Typer entry point for ``gbm-mx``."""

from __future__ import annotations

import datetime as _dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from gbm_mx_api import __version__
from gbm_mx_api.auth.session import DEFAULT_SESSION_PATH
from gbm_mx_api.cli._common import (
    die,
    echo_session_status,
    get_client,
)
from gbm_mx_api.cli._portfolio_md import (
    append_rows,
    existing_ids,
    render_new_rows,
)

app = typer.Typer(
    name="gbm-mx",
    help="Unofficial CLI for the GBM+ Mexican brokerage. Reverse-engineered, no warranty.",
    add_completion=False,
)
console = Console()


SessionPath = Annotated[
    str,
    typer.Option(
        "--session-path",
        help="Path to session.json",
        envvar="GBM_SESSION_PATH",
        show_default=True,
    ),
]


# ---------------------------------------------------------------------------
# Global options
# ---------------------------------------------------------------------------
@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Print version and exit.", is_eager=True),
    ] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------
@app.command()
def login(
    session_path: SessionPath = str(DEFAULT_SESSION_PATH),
) -> None:
    """Interactive login. Persists the session to disk."""
    client = get_client(session_path)
    echo_session_status(client.session)
    client.close()


# ---------------------------------------------------------------------------
# accounts ls
# ---------------------------------------------------------------------------
accounts_app = typer.Typer(no_args_is_help=True, help="Account/strategy operations.")
app.add_typer(accounts_app, name="accounts")


@accounts_app.command("ls")
def accounts_ls(session_path: SessionPath = str(DEFAULT_SESSION_PATH)) -> None:
    """List every strategy of the main contract."""
    with get_client(session_path) as client:
        main = client.contracts.get_main()
        accounts = client.accounts.list(main.contract_id)

    table = Table(title=f"Accounts for contract {main.legacy_contract_id}")
    table.add_column("Legacy ID")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")
    for a in accounts:
        pos = a.position.amount if a.position else 0
        pm = a.plus_minus.amount if a.plus_minus else 0
        pct = f"{a.plus_minus_percentage * 100:+.2f}%" if a.plus_minus_percentage else "—"
        table.add_row(
            a.legacy_contract_id,
            a.management_type_template,
            a.name or "—",
            f"{pos:,.2f}",
            f"{pm:+,.2f}",
            pct,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# positions
# ---------------------------------------------------------------------------
@app.command("positions")
def positions(
    session_path: SessionPath = str(DEFAULT_SESSION_PATH),
    legacy_id: Annotated[
        str | None,
        typer.Option("--legacy-id", help="Override the legacy account ID."),
    ] = None,
    raw: Annotated[
        bool, typer.Option("--raw", help="Dump the raw JSON instead of a table.")
    ] = False,
) -> None:
    """Show current portfolio composition for the trading account."""
    with get_client(session_path) as client:
        if legacy_id is None:
            main = client.contracts.get_main()
            trading = client.accounts.get_trading(main.contract_id)
            legacy_id = trading.legacy_contract_id
        summary = client.positions.summary(legacy_id)

    if raw:
        console.print_json(summary.model_dump_json())
        return

    table = Table(title=f"Positions for {legacy_id}")
    table.add_column("Ticker")
    table.add_column("Qty", justify="right")
    table.add_column("Avg price", justify="right")
    table.add_column("Last", justify="right")
    table.add_column("Market value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("Weight", justify="right")
    for p in summary.real_positions:
        table.add_row(
            p.issue_id,
            f"{p.quantity:g}",
            f"{p.average_price:,.2f}",
            f"{p.last_price:,.2f}",
            f"{p.market_value:,.2f}",
            f"{p.yield_value:+,.2f}",
            f"{p.position_percentage * 100:.2f}%",
        )
    console.print(table)
    console.print(f"\n[bold]Total portfolio value:[/] {summary.total_market_value:,.2f} MXN")


# ---------------------------------------------------------------------------
# orders ls
# ---------------------------------------------------------------------------
orders_app = typer.Typer(no_args_is_help=True, help="Order blotter operations.")
app.add_typer(orders_app, name="orders")


def _parse_date(value: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"Invalid date '{value}', expected YYYY-MM-DD.") from e


@orders_app.command("ls")
def orders_ls(
    since: Annotated[str, typer.Option("--since", help="Start date YYYY-MM-DD (inclusive).")],
    until: Annotated[
        str | None,
        typer.Option("--until", help="End date YYYY-MM-DD (inclusive). Defaults to today."),
    ] = None,
    legacy_id: Annotated[
        str | None,
        typer.Option("--legacy-id", help="Override the trading legacy id."),
    ] = None,
    session_path: SessionPath = str(DEFAULT_SESSION_PATH),
    output_json: Annotated[
        bool, typer.Option("--json", help="Output as JSON instead of a table.")
    ] = False,
) -> None:
    """List filled orders in a date range."""
    from_date = _parse_date(since)
    to_date = _parse_date(until) if until else _dt.date.today()

    with get_client(session_path) as client:
        if legacy_id is None:
            main = client.contracts.get_main()
            trading = client.accounts.get_trading(main.contract_id)
            legacy_id = trading.legacy_contract_id
        filled = client.orders.list_filled(legacy_id, from_date, to_date)

    if output_json:
        rows = [o.model_dump(mode="json") for o in filled]
        typer.echo(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
        return

    table = Table(title=f"Filled orders {from_date} → {to_date}")
    table.add_column("Date")
    table.add_column("Time")
    table.add_column("Ticker")
    table.add_column("Side")
    table.add_column("Qty", justify="right")
    table.add_column("Avg price", justify="right")
    table.add_column("Amount", justify="right")
    table.add_column("Commission", justify="right")
    table.add_column("ID")
    for o in filled:
        table.add_row(
            o.processed_at.date().isoformat(),
            o.processed_at.strftime("%H:%M:%S"),
            o.issue_id,
            o.side.name,
            str(o.quantity),
            f"{o.average_price:,.2f}",
            f"{o.amount:,.2f}",
            f"{o.commission:,.2f}",
            str(o.sob_id),
        )
    console.print(table)
    console.print(f"\n[bold]{len(filled)} filled orders[/]")


# ---------------------------------------------------------------------------
# dividends
# ---------------------------------------------------------------------------
dividends_app = typer.Typer(no_args_is_help=True, help="Dividend / cash-distribution operations.")
app.add_typer(dividends_app, name="dividends")


@dividends_app.command("ls")
def dividends_ls(
    since: Annotated[str, typer.Option("--since", help="Start date YYYY-MM-DD (inclusive).")],
    until: Annotated[
        str | None,
        typer.Option("--until", help="End date YYYY-MM-DD (inclusive). Defaults to today."),
    ] = None,
    legacy_id: Annotated[
        str | None,
        typer.Option("--legacy-id", help="Override the trading legacy id."),
    ] = None,
    include_isr: Annotated[
        bool,
        typer.Option(
            "--include-isr/--no-isr",
            help="Include ISR withholding rows alongside payouts.",
        ),
    ] = True,
    session_path: SessionPath = str(DEFAULT_SESSION_PATH),
    output_json: Annotated[
        bool, typer.Option("--json", help="Output as JSON instead of a table.")
    ] = False,
) -> None:
    """List dividend / cash-distribution movements in a date range."""
    from_date = _parse_date(since)
    to_date = _parse_date(until) if until else _dt.date.today()

    with get_client(session_path) as client:
        main = client.contracts.get_main()
        if legacy_id is None:
            trading = client.accounts.get_trading(main.contract_id)
            legacy_id = trading.legacy_contract_id
        items = client.dividends.list_for_range(main.contract_id, legacy_id, from_date, to_date)
    if not include_isr:
        items = [d for d in items if not d.is_withholding]

    if output_json:
        rows = [d.model_dump(mode="json") for d in items]
        typer.echo(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
        return

    table = Table(title=f"Dividends {from_date} → {to_date}")
    table.add_column("Date")
    table.add_column("Ticker")
    table.add_column("Description")
    table.add_column("Kind")
    table.add_column("Gross", justify="right")
    table.add_column("Net", justify="right")
    table.add_column("ID")
    net_total = Decimal("0")
    tax_total = Decimal("0")
    for d in items:
        kind = "ISR" if d.is_withholding else "Abono"
        table.add_row(
            d.process_date.date().isoformat(),
            d.security_id,
            d.transaction_description,
            kind,
            f"{d.transaction_amount:,.2f}",
            f"{d.transaction_net_amount:,.2f}",
            str(d.transaction_id),
        )
        if d.is_withholding:
            tax_total += d.transaction_amount
        else:
            net_total += d.transaction_net_amount
    console.print(table)
    console.print(
        f"\n[bold]{len(items)} movements[/] · "
        f"net received: [green]{net_total:,.2f}[/] · "
        f"ISR withheld: [red]{tax_total:,.2f}[/]"
    )


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------
@app.command("sync")
def sync(
    portfolio: Annotated[
        Path,
        typer.Argument(help="Path to Portfolio.md (will be appended to)."),
    ],
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Start date YYYY-MM-DD. Defaults to 60 days ago.",
        ),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="End date YYYY-MM-DD. Defaults to today."),
    ] = None,
    legacy_id: Annotated[
        str | None,
        typer.Option("--legacy-id", help="Override the trading legacy id."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be appended without writing."),
    ] = False,
    session_path: SessionPath = str(DEFAULT_SESSION_PATH),
) -> None:
    """Append filled orders that aren't already in Portfolio.md."""
    from_date = _parse_date(since) if since else _dt.date.today() - _dt.timedelta(days=60)
    to_date = _parse_date(until) if until else _dt.date.today()

    if from_date > to_date:
        die("--since must be <= --until.")

    existing = existing_ids(portfolio)
    console.print(f"[dim]Portfolio.md ya tiene {len(existing)} órdenes registradas.[/]")

    with get_client(session_path) as client:
        if legacy_id is None:
            main = client.contracts.get_main()
            trading = client.accounts.get_trading(main.contract_id)
            legacy_id = trading.legacy_contract_id
        filled = client.orders.list_filled(legacy_id, from_date, to_date)

    new_rows = render_new_rows(filled, skip_ids=existing)
    console.print(
        f"[dim]Rango {from_date} → {to_date}: {len(filled)} órdenes llenas, "
        f"{len(new_rows)} nuevas.[/]"
    )

    if not new_rows:
        console.print("[green]Nada que agregar.[/]")
        return

    if dry_run:
        console.print("[yellow]--dry-run, no se escribe nada:[/]\n")
        for row in new_rows:
            console.print(row)
        return

    append_rows(portfolio, new_rows)
    console.print(f"[green]OK Agregadas {len(new_rows)} filas a {portfolio}.[/]")


if __name__ == "__main__":
    app()
