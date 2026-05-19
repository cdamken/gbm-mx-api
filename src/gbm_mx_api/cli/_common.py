"""Shared helpers for the CLI subcommands."""

from __future__ import annotations

import getpass
import os
import sys
from typing import Annotated

import typer

from gbm_mx_api import GbmClient, MfaRequired, Session
from gbm_mx_api.auth.login import login as _login
from gbm_mx_api.auth.session import DEFAULT_SESSION_PATH

# Env var names the CLI honors when present (e.g. for CI / scripted runs).
ENV_EMAIL = "GBM_EMAIL"
ENV_PASSWORD = "GBM_PASSWORD"
ENV_CLIENT_ID = "GBM_CLIENT_ID"

# Reusable typer.Option for --session-path
SessionPathOpt = Annotated[
    str,
    typer.Option(
        "--session-path",
        help="Where the session.json lives.",
        envvar="GBM_SESSION_PATH",
        show_default=True,
    ),
]


def prompt_totp() -> str:
    """Ask the user for the 6-digit TOTP. Stays on stdin only — never logged."""
    code = input("Código de la app autenticadora (6 dígitos): ").strip()
    if not (code.isdigit() and len(code) == 6):
        typer.secho(
            "Error: Código inválido (deben ser 6 dígitos numéricos).", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=2)
    return code


def get_client(session_path: str) -> GbmClient:
    """Return a usable :class:`GbmClient`.

    Resolution order:
    1. Saved session at ``session_path`` if present and not expired.
    2. Interactive login (asks email/password if env vars are missing).
    Raises ``typer.Exit`` on user-facing errors (no traceback).
    """
    client = GbmClient.from_saved(session_path)  # type: ignore[arg-type]
    if client is not None:
        return client

    email = os.environ.get(ENV_EMAIL) or input("Email GBM+: ").strip()
    password = os.environ.get(ENV_PASSWORD) or getpass.getpass("Password GBM+: ")
    if not email or not password:
        typer.secho("Error: Faltan credenciales.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        session = _login(email, password, totp_provider=prompt_totp)
    except MfaRequired as e:
        # Should never reach here — login() handles the challenge internally.
        typer.secho(
            f"Error: Login failed: MFA challenge unresolved ({e})", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: Login failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    saved_at = session.save(session_path)  # type: ignore[arg-type]
    typer.secho(f"OK: Sesión guardada en {saved_at}", fg=typer.colors.GREEN, err=True)
    return GbmClient.from_session(session)


def echo_session_status(session: Session) -> None:
    """Print a one-liner about the session validity (to stderr)."""
    if session.is_expired:
        typer.secho("Sesión expirada.", fg=typer.colors.RED, err=True)
    else:
        m = session.seconds_remaining // 60
        typer.secho(f"Sesión válida ({m} min restantes).", fg=typer.colors.GREEN, err=True)


def default_session_path() -> str:
    """Resolve the default ``session.json`` location at runtime."""
    return str(DEFAULT_SESSION_PATH)


def die(message: str, code: int = 1) -> None:
    """Print an error to stderr and exit."""
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    sys.exit(code)
