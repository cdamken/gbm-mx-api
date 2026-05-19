# Changelog

Todas las versiones notables de `gbm-mx-api` van aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/), versionado
[SemVer](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/cdamken/gbm-mx-api/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.2
[0.1.1]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.1
[0.1.0]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.0
