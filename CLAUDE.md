# CLAUDE.md — gbm-mx-api

Contexto del proyecto para sesiones futuras de Claude Code u otros asistentes.
Léeme primero antes de modificar nada.

## Qué es este proyecto

Librería Python **no oficial** para la API interna de **GBM+** (Grupo Bursátil
Mexicano, casa de bolsa mexicana). Reverse-engineered. Publicada bajo MIT.

**Nombre del paquete:** `gbm-mx-api` (CLI: `gbm-mx`).

**Caso de uso primario que motivó el proyecto:** automatizar el mantenimiento
de un archivo `Portfolio.md` que el dueño llevaba a mano parseando correos
`.eml` de confirmación de orden. El CLI `gbm-mx sync` reemplaza ese flujo.
**El folder de datos del usuario vive aparte y nunca se versiona en este repo.**

**Idioma de las conversaciones con el usuario:** español. Código, commits y
docstrings en inglés (convención estándar Python).

## Estado actual — v0.1 funcional

| Fase | Estado |
|---|---|
| 0. Descubrimiento de endpoints | ✅ Completa (ver `docs/02-endpoints-discovered.md`) |
| 1. Diseño + scope MVP | ✅ Camino A (reemplazar correos) |
| 2. Código v0.1 | ✅ Auth + transport + domain + api + client + CLI |
| 3. Integración `Portfolio.md` | ✅ `gbm-mx sync <path>` |
| 4. Validación end-to-end | 🔄 En curso |
| 5. Publicación a PyPI | ⏳ Pendiente |

Calidad de v0.1: **60/60 tests, mypy --strict OK, ruff lint+format OK**.

## Estructura

```
gbm-mx-api/                            # repo público
├── CLAUDE.md, README.md, LICENSE, pyproject.toml, .gitignore
├── docs/
│   ├── 00-plan.md                     # plan por fases
│   ├── 01-discovery-plan.md           # guía Fase 0 (DevTools)
│   └── 02-endpoints-discovered.md     # hallazgos (anonimizados, valores sintéticos)
├── experiments/                       # gitignored — scripts ad-hoc + .env del usuario
│   └── (outputs/ con session.json, capturas, etc.)
├── src/gbm_mx_api/
│   ├── __init__.py, _version.py, py.typed, errors.py, client.py
│   ├── auth/                          # login + MFA TOTP + persistencia sesión
│   ├── transport/                     # HttpClient con geo, Bearer, retries, redacción
│   ├── domain/                        # Pydantic v2: Contract, Account, Order, Position
│   ├── api/                           # contracts, accounts, positions, orders
│   └── cli/                           # Typer entry: login, accounts, positions, orders, sync
└── tests/                             # pytest + respx, 60 tests
```

## Decisiones tomadas

| Decisión | Valor | Razón |
|---|---|---|
| Lenguaje | Python 3.10+ | Disponible donde quiera correrse; ecosistema brokers maduro |
| Visibilidad | Público en GitHub, MIT | Vale a la comunidad mexicana — no hay otra opción seria |
| Stack HTTP | `httpx` (sync) | Modern, sync+async ready si después se quiere extender |
| Modelos | Pydantic v2 inmutables (`frozen=True`) | Validación + seguridad |
| CLI | Typer + Rich | DX moderna; tables nativas |
| Tests | pytest + respx (HTTP mock) | 100% del flow sin tocar red real |
| Calidad | ruff + mypy --strict | No negociable |
| Credenciales | `.env` (gitignored) o stdin interactivo | Simple, sin keyring forzado |
| Persistencia sesión | `~/.gbm-mx/session.json` con `0600` | Estándar, atomic write |

## Hallazgos clave (resumen — detalles en `docs/02-endpoints-discovered.md`)

### Stack del backend
- **AWS Cognito** en `us-east-1` (pool `us-east-1_BKu7qAohu`) detrás de `auth.gbm.com`.
- Tres backends activos:
  - `auth.gbm.com/api/v1/...` — login (sin token).
  - `api.gbm.com/v1,v2/...` — REST moderno (contracts, accounts).
  - `homebroker-api.gbm.com/GBMP/api/...` — legacy con payload `{"request": ...}`.

### Requisitos sutiles
- Headers `device-latitude` / `device-longitude` son **obligatorios** en
  todas las requests (anti-fraude). Sin ellos, 400 antes de validar credenciales.
- `client_id` (`7c464570619a417080b300076e163289`) es **público** — sale en la
  URL de login. NO es un secreto, está hardcodeado como default.
- 2FA TOTP es el flow normal; el endpoint del challenge es
  `POST /api/v1/session/user/challenge` con `{clientid, user, session, code, challengeType}`.

### Endpoints implementados
- `GET /v1/contracts` → `Contract`.
- `GET /v2/contracts/{id}/accounts` → `list[Account]` (incluye P&L por estrategia).
- `POST /GBMP/Portfolio/GetPositionSummary` → `PortfolioSummary` (5 buckets).
- `POST /GBMP/Operation/GetBlotterOrders` → `list[Order]` por día.
  - **Acepta fechas pasadas** (gbmplus las hardcodeaba a hoy — era el bloqueador).
  - El rango from/to NO se honra → iteramos día por día en `list_filled`.

### Mapping Order → Portfolio.md
- `sob_id` (9 dígitos) → ID que coincide con los IDs de los correos viejos.
- `gbmIntProcessStatus`: 7 = Llena, 5 = Cancelada (otros valores no descubiertos).
- `bitBuy: true/false` → Compra/Venta.
- `processDate` ISO 8601 con timezone `-06:00` (CDMX).

## Privacidad — reglas duras

1. **`experiments/` y `discovery/` están gitignored** — pueden contener tokens,
   IDs reales, holdings. **Nunca commit.**
2. **`docs/02-endpoints-discovered.md` es público** — solo formas, nombres de
   campos, ejemplos sintéticos.
3. **Credenciales y tokens** nunca al repo. `.env` está en `.gitignore`;
   `.env.example` con placeholders ficticios sí va al repo.
4. **No mezclar repos.** Cuando el usuario quiera probar `gbm-mx sync`
   contra un Portfolio.md real, **siempre con un path absoluto que el
   usuario pase explícitamente** — el repo no debe hardcodear paths a
   directorios personales.
5. **Logging:** `transport/redaction.py` redacta tokens y campos sensibles
   automáticamente en debug logs.

## Disclaimers obligatorios

Ya en README:
- No oficial, no afiliada a Grupo Bursátil Mexicano.
- Hecha por reverse engineering de la app web pública.
- Endpoints pueden cambiar sin aviso.
- Credenciales y consecuencias financieras son responsabilidad del usuario.

## Cómo continuar

```bash
# Setup (en raíz del proyecto)
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,cli]"

# Calidad — todo debe pasar antes de commit
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src
.venv/bin/python -m pytest -q

# CLI — el caso de uso real
.venv/bin/gbm-mx --help
.venv/bin/gbm-mx login                          # interactivo, persiste sesión
.venv/bin/gbm-mx orders ls --since 2026-04-01
.venv/bin/gbm-mx sync <ruta-absoluta-a-Portfolio.md> --dry-run
```

## Trabajo pendiente para v0.2+

Ordenado por valor / esfuerzo:

1. **Refresh token** — usar `refresh_token` cuando el access expire para evitar
   re-MFA cada hora.
2. **Cash transactions** — endpoint conocido pero no implementado
   (`GET /v1/contracts/{main}/accounts/{id}/cash-transactions`).
3. **`gbm orders cancel <sob_id>`** — `POST /GBMP/Operation/CancelCapitalOrder`.
4. **Export multi-formato** — OFX `INVTRAN`, CSV compatible con Sharesight.
5. **Estados de cuenta PDF** — endpoint por descubrir.
6. **Catálogo BMV** — análogo al `getMarketsUSA` de gbmplus.
7. **Async client** — `AsyncGbmClient` para integraciones más exigentes.
8. **Schema fiscal mexicano** — ISR retenido, IVA, tipo de cambio DOF para
   constancia SAT.
