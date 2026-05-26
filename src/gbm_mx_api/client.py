"""Top-level facade: :class:`GbmClient`.

Bundles a configured :class:`HttpClient` plus the API modules that depend on
it. Typical usage::

    from gbm_mx_api import GbmClient

    # Easy: have the client log in for you, persisting the session.
    client = GbmClient.login(
        email="...",
        password="...",
        totp_provider=lambda: input("TOTP: "),
    )

    contracts = client.contracts.list()
    main = contracts[0]
    accounts = client.accounts.list(main.contract_id)
    trading = next(a for a in accounts if a.management_type_template == "trading")
    summary = client.positions.summary(trading.legacy_contract_id)
    filled = client.orders.list_filled(
        trading.legacy_contract_id,
        from_date=date(2026, 5, 1),
        to_date=date(2026, 5, 18),
    )
"""

from __future__ import annotations

from pathlib import Path

from gbm_mx_api.api.accounts import Accounts
from gbm_mx_api.api.contracts import Contracts
from gbm_mx_api.api.dividends import Dividends
from gbm_mx_api.api.orders import Orders
from gbm_mx_api.api.positions import Positions
from gbm_mx_api.api.transactions import Transactions
from gbm_mx_api.auth.login import TotpProvider
from gbm_mx_api.auth.login import login as _login
from gbm_mx_api.auth.session import DEFAULT_SESSION_PATH, Session
from gbm_mx_api.errors import GbmError
from gbm_mx_api.transport.http import HttpClient


class GbmClient:
    """Authenticated, ready-to-use GBM API client.

    Don't construct directly — use one of:

    - :classmethod:`login` (interactive, with TOTP callback)
    - :classmethod:`from_session` (reuse a previously-saved session)
    - :classmethod:`from_saved` (one-shot: load if present and still valid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._http = HttpClient(
            latitude=session.latitude,
            longitude=session.longitude,
            access_token=session.access_token,
        )
        self.contracts = Contracts(self._http)
        self.accounts = Accounts(self._http)
        self.positions = Positions(self._http)
        self.orders = Orders(self._http)
        self.dividends = Dividends(self._http)
        self.transactions = Transactions(self._http)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def from_session(cls, session: Session) -> GbmClient:
        """Build a client from an already-issued :class:`Session`."""
        if session.is_expired:
            raise GbmError("Session is expired; obtain a new one with GbmClient.login().")
        return cls(session)

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        *,
        totp_provider: TotpProvider,
        persist_to: Path | None = DEFAULT_SESSION_PATH,
    ) -> GbmClient:
        """Run the full login flow and return a ready client.

        If ``persist_to`` is not None, the resulting session is saved to that
        path so subsequent runs can reuse it (default
        ``~/.gbm-mx/session.json``).
        """
        session = _login(email, password, totp_provider=totp_provider)
        if persist_to is not None:
            session.save(persist_to)
        return cls(session)

    @classmethod
    def from_saved(cls, path: Path = DEFAULT_SESSION_PATH) -> GbmClient | None:
        """Load a persisted session if present and still valid.

        Returns ``None`` if no usable session exists. The caller can then
        decide to call :meth:`login` interactively.
        """
        session = Session.try_load(path)
        if session is None or session.is_expired:
            return None
        return cls(session)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @property
    def session(self) -> Session:
        return self._session

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GbmClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
