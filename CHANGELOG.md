# Changelog

Todas las versiones notables de `gbm-mx-api` van aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/), versionado
[SemVer](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/cdamken/gbm-mx-api/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cdamken/gbm-mx-api/releases/tag/v0.1.0
