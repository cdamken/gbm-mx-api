# Changelog

Todas las versiones notables de `gbm-mx-api` van aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/), versionado
[SemVer](https://semver.org/).

## [Unreleased]

## [0.3.0] — 2026-06-02

### Added

- ``gbm_mx_api.auth.refresh_session(session)``: silent refresh via Cognito
  ``REFRESH_TOKEN_AUTH``. Mints a new access/identity token using the
  ``refresh_token`` stored in the session — no TOTP prompt required.
  The refresh token itself stays valid for ~30 days (Cognito default),
  so users now go from "TOTP every hour" to "TOTP roughly once a month".
- ``GbmClient.from_saved()`` now auto-refreshes expired sessions when a
  refresh token is available. If the refresh succeeds, the refreshed
  session is persisted back to disk. If it fails (token revoked, Cognito
  down), returns ``None`` so the caller can fall back to interactive
  TOTP login. This was the long-pending #1 v0.2 follow-up item.

## [0.2.6] — 2026-06-01

### Fixed

- ``complete_mfa`` now ALWAYS reclassifies HTTP 422 from the
  ``/challenge`` endpoint as ``AuthError``, regardless of the response
  body shape. Previously the classifier required a dict body with
  ``id: "NotAuthorizedException"``; when GBM returned 422 with a
  different body (empty, bare string), the error surfaced as a generic
  ``ApiError`` which the dashboard couldn't recognize as "invalid TOTP"
  and showed as "API error" instead of reopening the TOTP modal.

## [0.2.5] — 2026-06-01

### Fixed

- Transient DNS or TCP connect failures on POST endpoints (notably
  ``/api/v1/session/user`` during login) were not retried, surfacing as
  a hard ``TransportError`` like ``[Errno -3] Temporary failure in name
  resolution``. These errors happen BEFORE the request leaves the
  client, so retrying is safe even for non-idempotent verbs.
  - Connect-time errors (``httpx.ConnectError``, ``ConnectTimeout``)
    now retry up to ``max_retries`` for every HTTP method.
  - Read timeouts on writes still don't retry (the server may have
    processed the request even though we missed the response).

## [0.2.4] — 2026-06-01

### Added — external transfer categories on Transaction.category

Discovered when investigating a real-world case: a transfer from one
GBM account holder to a different GBM account holder ("Transferencia
Recibida GBM", ``sub_transaction_type=3867``) was being miscategorized
as ``"other"`` because the prior logic only handled the
``"DEPOSITO/RETIRO POR TRASPASO"`` (same-titular) descriptions.

- New ``Transaction.category`` values:
  - ``"external_deposit"`` — money received from another GBM customer.
  - ``"external_withdrawal"`` — money sent to another GBM customer.
- New helper ``Transaction.is_external_transfer``.
- Detection is by description (``"recibida"|"enviada"`` + ``"gbm"``);
  see ``domain/transaction.py:category``.

## [0.2.3] — 2026-06-01

### Fixed

- ``Dashboard.investments_groups`` was timing out with the default 15 s
  client timeout because the v3 endpoint joins live FX + homebroker +
  offshore data server-side and can take 20-30 s on a slow path.
  - ``HttpClient.get`` and ``.post`` now accept an optional ``timeout``
    kwarg for per-call overrides.
  - The investments-groups call uses a 60 s timeout.

## [0.2.2] — 2026-06-01

### Added — Dashboard "investments-groups" endpoint

Discovered via HAR export: the GBM mobile app's "TOTAL INVERTIDO" number
comes from ``GET https://api.appgbm.com/v3/dashboard/contracts/{id}/investments-groups?email={email}``
which returns server-computed group balances using the "live" FX rate.

This endpoint and the legacy ``/GBMP/Portfolio/GetPositionSummary`` use
DIFFERENT FX rates for USD-denominated holdings (notably Trading USA's
fractional shares). On a portfolio with ~$28k USD in DRAM the two
diverge by ~$1,000 MXN over a typical day. This v3 endpoint matches
what the user sees in the GBM mobile app to the cent.

**API changes:**

- New ``client.dashboard.investments_groups(contract_id, email)``.
- New domain models ``InvestmentsGroups``, ``Group`` (with optional
  per-currency ``positions`` for offshore holdings).
- Exported at the package root.

**Group types observed:** ``smart_cash``, ``smart_cash_usd``,
``instruments`` (= Trading MX), ``offshore`` (= Trading USA),
``goals`` (= GBM Advisory).

### Tests

- 80/80 passing (2 new for Dashboard).

## [0.2.1] — 2026-06-01

### Added — appgbm.com dashboard accounts endpoint

Discovered via DevTools on www.appgbm.com that the legacy
``api.gbm.com/v2/contracts/{id}/accounts`` endpoint **omits** the
Smart Cash USD account (``management_type_template=wealth``). The
appgbm.com dashboard uses a different endpoint that returns all five
accounts including the hidden one.

**API changes:**

- ``Account`` now has an ``is_smart_cash_usd: bool`` field.
- ``client.accounts.list_dashboard(contract_id)`` — calls
  ``api.appgbm.com/v1/dashboard/contracts/{id}/accounts`` and returns
  the full list of accounts (metadata only, no balances).
- ``client.accounts.list_with_dashboard(contract_id)`` — merges the
  full list from ``list_dashboard`` with the balances from the legacy
  ``list``. Use this when you want both completeness and balance data.

### Documentation

- ``docs/02-endpoints-discovered.md`` — new section documenting the
  appgbm.com dashboard endpoints (``/v1/dashboard/contracts/{id}/accounts``,
  ``/v1/dashboard/parties/{party_uuid}``, the SUNSET endpoint, and the
  Smart Cash investments-group endpoint that is still undiscovered).
- Explained that GBM's "TOTAL INVERTIDO" is calculated client-side by
  summing balances; there is no single endpoint to map.
- Added a reverse-engineering protocol for future discovery sessions.

## [0.2.0] — 2026-05-26

### Added — full transactions ledger

Generalizes the dividend-only view of `api.appgbm.com/v2/.../transactions`
into a full ledger client that returns **every** movement: stock buys
and sells, fund buys and sells, repos, cash transfers (deposit /
withdrawal), FX, and dividend-style entries. This unblocks visibility
for accounts that `GetBlotterOrders` cannot see (Asesor, Smart Cash) —
the blotter endpoint is effectively Personal-only.

**API changes:**

- `client.transactions.list_for_range(contract_id, legacy_contract_id, from_date, to_date)`
  — paginated full-ledger fetch. Same endpoint as `Dividends`, but with
  no `transac_type` filter (the backend ignores it except for the
  literal value `"dividend"`).
- New domain model `Transaction` exported from the package root, with a
  computed `.category` property classifying each row into one of:
  `buy_stock`, `sell_stock`, `buy_fund`, `sell_fund`, `repo_buy`,
  `repo_mature`, `deposit`, `withdrawal`, `fx`, `dividend`,
  `tax_withholding`, `other`. Convenience helpers `is_buy`, `is_sell`,
  `is_cash_flow`.

**Discovery notes (`docs/02-endpoints-discovered.md`):**

- `transac_type` is essentially ignored by the backend except for the
  literal value `"dividend"`. Filter on the response side using
  `transaction_type` + `sub_transaction_type` + `transaction_description`.
- `GetBlotterOrders` (homebroker-api) does NOT support secondary
  accounts. Passing the secondary account's `legacy_account_id` as
  `contractId` returns 0 items, and passing the `accountId` UUID
  alongside is also ignored. The blotter is effectively Personal-only.

### Tests

- 78/78 passing (7 new tests for the Transactions client).

## [0.1.6] — 2026-05-22

### Added

- `gbm-mx dividends ls` CLI command — mirrors `orders ls` but for cash
  distributions. `--include-isr` / `--no-isr` toggles whether ISR
  withholding rows show up alongside payouts.
- `Dividend` model is now exported from the package root
  (`from gbm_mx_api import Dividend`).

### Fixed

- `auth/login.py`: `latitude=0.0` (equator) and `longitude=0.0` (Greenwich
  meridian) are now treated as valid user-provided values instead of
  being clobbered by auto-detected geo. Uses explicit ``None`` check.
- `domain/order.py`: `Order.status_label` now returns Spanish labels
  (`"Llena"`, `"Cancelada"`) consistent with the rest of the codebase
  and the GBM web UI. Was returning English (`"Filled"`, `"Cancelled"`).
- `api/dividends.py`: pagination loop now stops when the backend returns
  empty `items`, even if `pagination_metadata.next` is still non-empty.
  Previously could waste up to `_MAX_PAGES` (200) HTTP requests on a
  misbehaving backend.
- `auth/session.py`: `Session.try_load()` now logs a warning when the
  session file exists but is unreadable (permissions, corrupted JSON,
  schema mismatch after a model bump). A missing file stays silent as
  before — that's the normal first-run path.

### Changed

- `api/orders.py`: removed two dead `try/except ApiError: raise` blocks
  in `list_for_range` and `list_filled`. The exception propagates
  unchanged either way; the dead blocks just added noise.

### Tests

- Still 71/71 (no new tests, but `test_status_label_known_values` was
  updated to expect the new Spanish labels).

## [0.1.5] — 2026-05-22

### Added — dividend / cash-distribution endpoint

Discovered the data source behind the "Dividendos" tab on the basic
appgbm.com web app. It lives on a **different backend host**
(`api.appgbm.com`) from the rest of the API surface we use
(`api.gbm.com`, `homebroker-api.gbm.com`).

**API changes:**

- `client.dividends.list_for_range(contract_id, legacy_contract_id, from_date, to_date)`
  — returns every cash-flow GBM classifies as a dividend in the range:
  cash dividends, capital returns, "Resultado Fiscal Distribuido",
  matching ISR (tax) withholding lines, etc. Pagination is handled
  transparently.
- New `Dividend` Pydantic model with `transaction_id`, `security_id`
  (ticker), `transaction_amount` / `transaction_net_amount` (MXN),
  `process_date`, `transaction_description`, plus a convenience
  `is_withholding` property to tell ISR rows apart from gross payouts.

### Tests

- 71 total (was 65) — 6 new tests covering single-page, pagination,
  param shape, de-duplication, range validation, and the
  `is_withholding` property.

## [0.1.4] — 2026-05-21

### Changed

- `start_login` and `complete_mfa` now translate GBM's HTTP 422
  `NotAuthorizedException` into an `AuthError` instead of a generic
  `ApiError`. GBM uses 422 (not the conventional 401) for wrong
  credentials and wrong/expired TOTP codes; catching this lets callers
  show a "reauthenticate" UI instead of a scary "API failed" message.
- The `AuthError` raised in this case preserves GBM's Spanish message
  (e.g. *"Verifica tu correo y contraseña."*) so the UI can show it
  verbatim.

### Tests

- 1 new test covering the 422 → AuthError reclassification (65 total).

## [0.1.3] — 2026-05-20

### Added

- `Orders.list_for_range(legacy_id, from_date, to_date)` — returns every
  order (any status) submitted in the range, not just filled ones.
  Same per-day iteration + dedupe behavior as `list_filled`.
- `Order.is_cancelled` — convenience property mirroring `is_filled`.
- `Order.status_label` — Spanish-friendly label for the status code.
  Returns `"Filled"`, `"Cancelled"`, or `"Estado N"` for unknowns.

### Changed

- `Order.status` is now a plain `int` instead of a strict `OrderStatus`
  enum. Parsing no longer fails when GBM returns an unknown status code
  (e.g. partially-filled, pending). The previously-known values
  (5=Cancelada, 7=Llena) still work as expected via `is_filled` /
  `is_cancelled` / `status_label`. **Breaking** for callers that did
  `order.status is OrderStatus.FILLED`; use `order.is_filled` or compare
  against `OrderStatus.FILLED.value` instead.

### Tests

- 64 total (was 62) — 2 new tests covering unknown status values and
  `status_label`.

## [0.1.2] — 2026-05-19

### Changed — license

- License changed from **MIT** to **Business Source License 1.1** (SPDX
  `BUSL-1.1`). Personal, educational and internal use remain permitted
  without restriction; offering the Licensed Work as a hosted or embedded
  competitive service requires a separate agreement.
- Change Date: `2030-05-19`. On that date, this version auto-relicenses to
  Apache License 2.0.
- Versions `0.1.0` and `0.1.1` were released under MIT and remain so —
  this change applies to `0.1.2` and onward.

No code changes; the license update is the only difference vs `0.1.1`.

## [0.1.1] — 2026-05-19

### Added — multi-account position support

Discovered via probing during dashboard work that `GetPositionSummary`
accepts an extra `accountId` (UUID) field. With it, the endpoint also
returns positions for non-primary accounts (Asesor, Trading USA) and
exposes two new sections that didn't appear in the primary-account
response.

**API changes:**
- `Positions.summary(legacy_account_id, account_id=...)` — new optional
  `account_id` parameter. Send the `Account.account_id` UUID to get
  full holdings for Asesor / Trading USA accounts.
- `PortfolioSummary` model — two new fields:
  - `sociedades_inversion_comun` (alias `sociedadesInversionComun`) —
    mutual funds (e.g. GBMAAA BO). Surfaces on Asesor accounts.
  - `mercado_extranjero` (alias `mercadoExtranjero`) — USA fractional
    shares. Surfaces on `trading_usa` accounts.
- `PortfolioSummary.real_positions` now includes the two new sections.
- `PositionValueType` enum — added members:
  - `COMUN = 2` (sociedades de inversión común)
  - `EXTRANJERO = 100` (mercado extranjero / fractional shares)

Backwards compatible: existing callers that don't pass `account_id`
continue to work identically.

### Tests

- 2 new tests covering the `account_id` parameter and the new sections.
- 62 total tests passing.

## [0.1.0] — 2026-05-19

### Added — primera versión alpha funcional

**Autenticación:**
- Login completo con email + password + 2FA TOTP (`SOFTWARE_TOKEN_MFA`).
- Detección automática de geolocalización por IP (requerido por GBM).
- Persistencia de sesión en `~/.gbm-mx/session.json` con permisos `0600`.
- Lectura/escritura atómica del archivo de sesión.

**Endpoints de lectura cubiertos:**
- `GET /v1/contracts` → `Contract`.
- `GET /v2/contracts/{contract_id}/accounts` → `list[Account]` con P&L.
- `POST /GBMP/Portfolio/GetPositionSummary` → `PortfolioSummary` con 5 buckets.
- `POST /GBMP/Operation/GetBlotterOrders` → `list[Order]` por día.
  - **Soporta `processDate` con fechas pasadas** (corrige bloqueador de `gbmplus`).
  - Helper `list_filled(from_date, to_date)` itera día por día.

**Modelos tipados** (Pydantic v2 inmutables):
- `Contract`, `Account`, `Money`, `Order`, `FilledOrder`, `Position`,
  `PortfolioSummary`, `Session`.
- Enums: `OrderStatus`, `Side`, `InstrumentType`, `AccountType`,
  `PositionValueType`.

**CLI** (`gbm-mx`):
- `gbm-mx login` — login interactivo persistente.
- `gbm-mx accounts ls` — tabla con estrategias y P&L.
- `gbm-mx positions` — composición actual del portafolio.
- `gbm-mx orders ls --since --until` — listado de órdenes llenas.
- `gbm-mx sync <Portfolio.md>` — append incremental al archivo Markdown,
  deduplicado por `ID de la orden`.

**Transport / calidad:**
- HTTP client con retries en 5xx idempotentes, respeto a `Retry-After` en 429,
  headers geo automáticos.
- Logging con redacción automática de tokens y campos personales.
- `py.typed` marker (PEP 561).
- 60 tests con `respx` (cero red real).
- `mypy --strict` clean.
- `ruff check + format` clean.

**Documentación:**
- README en español con quickstart.
- `docs/00-plan.md` — plan general.
- `docs/01-discovery-plan.md` — guía Fase 0 (DevTools).
- `docs/02-endpoints-discovered.md` — referencia técnica.
- `docs/03-usage.md` — tutorial detallado.
- `docs/04-development.md` — guía para contribuidores.
- `CLAUDE.md` — contexto para asistentes AI.

### Known limitations

- **No hay refresh token automático** — re-login manual después de ~1h.
- **No envía / cancela órdenes** — solo lectura por ahora (decisión consciente).
- **No expone USA fractional shares** todavía (existen los endpoints en
  `gbmplus`, planeado para v0.2).
- `list_filled` itera día por día — puede ser lento para rangos > 90 días.

### Project infrastructure

- Repo público bajo licencia MIT.
- Python 3.10+.
- Dependencias mínimas: `httpx`, `pydantic`. CLI extras: `typer`, `rich`.

[Unreleased]: https://github.com/cdamken/gbm-mx-api/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.6
[0.1.5]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.5
[0.1.4]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.4
[0.1.3]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.3
[0.1.2]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.2
[0.1.1]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.1
[0.1.0]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.0
