# gbm-mx-api — Plan del proyecto

Librería Python no oficial para la API interna de GBM+ (casa de bolsa
mexicana). Reverse-engineered. No afiliada a Grupo Bursátil Mexicano.

## Estado por fase

| Fase | Objetivo | Estado |
|---|---|---|
| **0. Descubrimiento** | Catalogar endpoints reales con DevTools / pruebas. | ✅ Completa |
| **1. Diseño v0.1** | Definir alcance MVP — Camino A: reemplazar correos. | ✅ Completa |
| **2. Implementación v0.1** | Auth + transport + domain + api + client + CLI + tests. | ✅ Completa |
| **3. Integración** | CLI `gbm-mx sync <portfolio.md>` validado end-to-end. | ✅ Completa |
| **4. Publicación** | Repo público en GitHub, primer release alpha en PyPI. | ⏳ Pendiente |
| **5. Crecimiento (v0.2+)** | Cobertura adicional según uso real. | 📋 Backlog |

## v0.1 entregado

Lo que existe y funciona (validado end-to-end contra GBM real):

- **Auth con 2FA TOTP** (`SOFTWARE_TOKEN_MFA`).
- **Histórico de órdenes llenas** iterando día por día.
- **Posiciones** con P&L por instrumento.
- **Cuentas / estrategias** del contrato con valores y P&L.
- **CLI**: `login`, `accounts ls`, `positions`, `orders ls`, `sync`.
- **60 tests** (mypy --strict OK, ruff clean).

Ver [`CHANGELOG.md`](../CHANGELOG.md) y [`docs/03-usage.md`](03-usage.md).

## Roadmap v0.2+

Backlog ordenado por valor:

| Item | Por qué |
|---|---|
| Refresh token | Eliminar la fricción de re-loguearse cada hora. |
| `cash-transactions` | Endpoint conocido (de gbmplus) — depósitos, retiros, dividendos, ISR. |
| Export OFX / CSV | Compatibilidad con Sharesight, Snowball, Trademetria (que hoy no soportan brokers MX). |
| Cancel order | `POST /GBMP/Operation/CancelCapitalOrder`. |
| Submit order | Solo después de validación legal/contractual cuidadosa. |
| USA fractional shares | Endpoints conocidos en `gbmplus`. |
| Estados de cuenta PDF | Endpoint por descubrir. |
| Esquema fiscal MX | ISR, IVA, DOF — habilita constancia fiscal SAT. |
| Async client | Para integraciones más exigentes. |

## Referencias (resultado de la fase 0)

- Única librería pública existente para GBM: `markzuckerbergas/gbmplus-api-python`.
  No soporta 2FA ni histórico de órdenes — esa fue la motivación para
  `gbm-mx-api`.
- Backends activos de GBM:
  - `https://auth.gbm.com/api/v1/...` (Cognito wrapper, sin token).
  - `https://api.gbm.com/v1,v2/...` (REST moderno, Bearer).
  - `https://homebroker-api.gbm.com/GBMP/api/...` (legacy RPC, Bearer).
  - `https://api.trading-usa.gbm.com/v1/...` (USA, no implementado todavía).
- Stack de identidad: **AWS Cognito** en `us-east-1`.
- Ver [`02-endpoints-discovered.md`](02-endpoints-discovered.md) para detalles.

## Disclaimers

- No oficial, no afiliada a Grupo Bursátil Mexicano.
- Hecha por reverse engineering de la app web pública.
- Endpoints pueden cambiar sin aviso.
- Uso bajo responsabilidad propia.
