# gbm-mx-api

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

Cliente Python **no oficial** para la API interna de **GBM+**, la casa de bolsa
mexicana de Grupo Bursátil Mexicano. Hecho por ingeniería inversa de la app web
pública.

```bash
pip install "gbm-mx-api[cli]"
gbm-mx login
gbm-mx orders ls --since 2026-04-01
```

> ⚠️ **No oficial.** No está afiliada, endorsed ni patrocinada por Grupo Bursátil
> Mexicano. Los endpoints pueden cambiar sin aviso. Las credenciales del usuario
> y las consecuencias financieras de cualquier operación enviada con esta
> librería son **responsabilidad exclusiva de quien la usa**. Verifica los
> Términos de Servicio de tu contrato antes de automatizar nada.

---

## ¿Qué hace?

- **Login con 2FA TOTP** (la mayoría de cuentas GBM lo tienen).
- **Histórico de órdenes llenas** filtradas por fecha — la pieza clave que
  ninguna otra librería pública para GBM expone hoy.
- **Posiciones actuales del portafolio** con P&L por instrumento.
- **Cuentas / estrategias** del contrato (Trading MX, Trading USA, Smart Cash).
- **Sync incremental a un `Portfolio.md`** propio — agrega solo órdenes nuevas,
  deduplicadas por ID de orden.

Pensada para personas que quieren tener una copia local de sus datos de GBM o
automatizar el seguimiento de su portafolio.

## Instalación

```bash
# Solo la librería (Python API):
pip install gbm-mx-api

# Con el CLI (recomendado):
pip install "gbm-mx-api[cli]"

# Desde el repo (desarrollo):
git clone https://github.com/cdamken/gbm-mx-api.git
cd gbm-mx-api
pip install -e ".[dev,cli]"
```

Requiere Python 3.10 o superior.

## Quickstart

### CLI

```bash
# 1. Login (interactivo, te pide email/password/TOTP la primera vez)
gbm-mx login

# 2. Ver tus cuentas
gbm-mx accounts ls

# 3. Composición actual del portafolio
gbm-mx positions

# 4. Listar órdenes llenas de un rango
gbm-mx orders ls --since 2026-04-01 --until 2026-05-19

# 5. Sincronizar tu Portfolio.md (dry-run primero para previsualizar)
gbm-mx sync /ruta/a/Portfolio.md --since 2026-04-01 --dry-run
gbm-mx sync /ruta/a/Portfolio.md --since 2026-04-01
```

Después del primer `login`, la sesión se guarda en `~/.gbm-mx/session.json`
(permisos `0600`) y dura ~1 hora. Los siguientes comandos la reutilizan.

### Python API

```python
from datetime import date
from gbm_mx_api import GbmClient

client = GbmClient.login(
    email="tu-email@dominio.com",
    password="tu-contraseña",
    totp_provider=lambda: input("Código TOTP: "),
)

# Contrato y cuenta principal
main = client.contracts.get_main()
trading = client.accounts.get_trading(main.contract_id)

# Composición del portafolio
summary = client.positions.summary(trading.legacy_contract_id)
print(f"Valor total: ${summary.total_market_value:,.2f} MXN")
for p in summary.real_positions:
    print(f"  {p.issue_id:15s} {p.quantity:>8} @ {p.last_price:,.2f}")

# Órdenes llenas de un rango (itera día por día internamente)
filled = client.orders.list_filled(
    trading.legacy_contract_id,
    from_date=date(2026, 4, 1),
    to_date=date(2026, 5, 19),
)
for o in filled:
    print(f"{o.processed_at} {o.issue_id:15s} {o.side.name} {o.quantity} @ {o.average_price}")

client.close()
```

## Documentación

- **[docs/03-usage.md](docs/03-usage.md)** — Guía de uso paso a paso (CLI y Python API).
- **[docs/04-development.md](docs/04-development.md)** — Cómo contribuir, correr tests, estructura del código.
- **[docs/02-endpoints-discovered.md](docs/02-endpoints-discovered.md)** — Cómo se descubrió la API (referencia técnica).
- **[CHANGELOG.md](CHANGELOG.md)** — Historial de versiones.

## Credenciales y privacidad

| Dato | Cómo se maneja |
|---|---|
| Email + password | Variables de entorno `GBM_EMAIL` / `GBM_PASSWORD`, o prompts interactivos. **Nunca al repo.** |
| Código TOTP | Solo en stdin del prompt cada login. Nunca persistido. |
| Tokens (access/identity/refresh) | `~/.gbm-mx/session.json` con permisos `0600`. Atomic write. |
| `client_id` de GBM | Hardcodeado en la lib — es público (visible en URL de login). |
| Geolocalización | Detectada por IP en cada login (anti-fraude que GBM exige). Se puede fijar con `GBM_LATITUDE` / `GBM_LONGITUDE`. |

Los logs en modo debug redactan automáticamente tokens y campos sensibles.

## Estado y alcance

**v0.1.0** — Alpha funcional. Cubre:

- ✅ Login completo (incluido 2FA TOTP).
- ✅ Lectura: contratos, cuentas, posiciones, blotter de órdenes con histórico.
- ✅ CLI con 5 subcomandos incluyendo `sync`.
- ✅ 60 tests pasando, mypy strict, ruff verde.

**Limitaciones conocidas de v0.1:**

- El backend solo devuelve órdenes **por día** — `list_filled` itera y agrupa.
  En rangos grandes (90+ días) puede ser lento.
- No hay refresh de token automático: cuando la sesión expira (~1h), hay que
  hacer `gbm-mx login` de nuevo.
- Solo lectura. **No envía ni cancela órdenes** desde la lib (sería trivial
  agregar técnicamente, pero los riesgos legales / financieros aconsejan
  esperar y empezar por solo-lectura).

**Roadmap v0.2+:**

- Refresh token.
- Movimientos de efectivo (`/cash-transactions`).
- Export a OFX / CSV (formato Sharesight).
- Estados de cuenta PDF.
- Esquema fiscal mexicano (ISR, IVA, DOF) para constancias SAT.

Ver [CHANGELOG.md](CHANGELOG.md).

## Comparación

| Feature | [`gbmplus`](https://github.com/markzuckerbergas/gbmplus-api-python) | `gbm-mx-api` |
|---|:-:|:-:|
| Login con 2FA TOTP | ❌ | ✅ |
| Histórico de órdenes (no solo "hoy") | ❌ | ✅ |
| Modelos tipados (Pydantic v2) | ❌ | ✅ |
| `py.typed` marker | ❌ | ✅ |
| CLI integrado | ❌ | ✅ |
| Tests | ❌ | ✅ (60) |
| Sincronización a `Portfolio.md` | ❌ | ✅ |
| Redacción de tokens en logs | ❌ | ✅ |
| Envío de órdenes / transferencias | ✅ | ❌ (planeado) |
| USA fractional shares | ✅ | ❌ (planeado) |

Si necesitas enviar órdenes o usar USA fractional shares hoy, `gbmplus` sigue
siendo útil. Si tu caso es leer datos históricos o automatizar tracking,
`gbm-mx-api` es lo que buscas.

## ¿Por qué existe?

GBM no publica una API para clientes. Hasta esta librería, la única alternativa
era `gbmplus` (también no oficial), que no soporta 2FA ni histórico de órdenes.
Faltaba algo:

- Con 2FA, porque la mayoría de cuentas GBM lo tienen activado.
- Con histórico, porque sin él no se puede automatizar tracking de portafolio.
- Con calidad (tests, tipos, CLI), porque mantener código a largo plazo
  requiere esa base.

`gbm-mx-api` se inspira en [`alpaca-py`](https://github.com/alpacahq/alpaca-py),
[`ib_async`](https://github.com/ib-api-reloaded/ib_async) y
[`kiteconnect`](https://github.com/zerodha/pykiteconnect) — librerías Python
de brokers en otros mercados (US, EU, India) — adaptado al stack mexicano.

## Disclaimers

- **No oficial / Unofficial.** Esta librería no está endorsed ni afiliada con
  Grupo Bursátil Mexicano. El uso del nombre "GBM" es solo descriptivo.
- **Hecha por reverse engineering** de la app web pública (`homebroker-pro.gbm.com`).
- **Los endpoints pueden cambiar sin aviso** — ese es el riesgo de una API
  no oficial.
- **Verifica los Términos de Servicio** de tu contrato con GBM antes de
  automatizar nada. El uso de clientes no oficiales puede violar esos términos.
- **El autor no se hace responsable** por pérdidas financieras, problemas
  contractuales, o cualquier otra consecuencia del uso de esta librería.

## Licencia

[MIT](LICENSE) — uso libre con atribución.
