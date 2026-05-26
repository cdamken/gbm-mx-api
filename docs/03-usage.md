# Guía de uso — gbm-mx-api

Tutorial paso a paso del CLI y de la API Python. Asume que la instalación está
hecha (`pip install "gbm-mx-api[cli]"`).

> Si vienes del README y solo quieres correr cosas rápidas, ese es suficiente.
> Este documento entra en detalle: opciones, troubleshooting, escenarios reales.

## Tabla de contenidos

1. [Setup inicial](#setup-inicial)
2. [CLI](#cli)
   - [`gbm-mx login`](#gbm-mx-login)
   - [`gbm-mx accounts ls`](#gbm-mx-accounts-ls)
   - [`gbm-mx positions`](#gbm-mx-positions)
   - [`gbm-mx orders ls`](#gbm-mx-orders-ls)
   - [`gbm-mx dividends ls`](#gbm-mx-dividends-ls)
   - [`gbm-mx sync`](#gbm-mx-sync)
3. [Python API](#python-api)
4. [Variables de entorno](#variables-de-entorno)
5. [Persistencia de sesión](#persistencia-de-sesión)
6. [Troubleshooting](#troubleshooting)

---

## Setup inicial

### 1. Credenciales

Hay tres formas de pasar tu email + password (en orden de preferencia):

- **Variables de entorno**:
  ```bash
  export GBM_EMAIL="tu-email@dominio.com"
  export GBM_PASSWORD="tu-contraseña"
  ```
- **Archivo `.env`** en el directorio de trabajo:
  ```ini
  GBM_EMAIL=tu-email@dominio.com
  GBM_PASSWORD=tu-contraseña
  ```
  Cárgalo con `set -a; source .env; set +a` antes de correr los comandos.
- **Prompts interactivos**. Si las dos anteriores no están, el CLI te las pide.

> El **código TOTP** (6 dígitos de la app autenticadora) **siempre** se pide por
> stdin. Nunca se persiste.

### 2. Primera ejecución

```bash
gbm-mx login
```

Output esperado:
```
Código de la app autenticadora (6 dígitos): 123456
OK: Sesión guardada en /Users/<tú>/.gbm-mx/session.json
Sesión válida (60 min restantes).
```

A partir de aquí, durante una hora, los demás comandos usan la sesión guardada
y no piden TOTP otra vez.

---

## CLI

### `gbm-mx login`

Login interactivo. Solo necesario una vez por hora (o cuando la sesión expire).

**Opciones:**
- `--session-path PATH` — dónde guardar `session.json`. Default:
  `~/.gbm-mx/session.json`. También configurable con `GBM_SESSION_PATH`.

**Ejemplo con sesión persistida en otro lugar:**
```bash
gbm-mx login --session-path /tmp/mi-sesion.json
gbm-mx accounts ls --session-path /tmp/mi-sesion.json
```

Útil para tener sesiones separadas por cuenta (rara, pero posible).

---

### `gbm-mx accounts ls`

Lista las estrategias del contrato principal con su valor actual y P&L.

```bash
gbm-mx accounts ls
```

Output ejemplo:
```
                       Accounts for contract AB12CD
┏━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┓
┃ Legacy ID ┃ Type        ┃ Name        ┃      Value ┃       P&L ┃  P&L % ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━┩
│ AB12CD05  │ trading     │ Personal    │ 152,240.19 │ +3,292.88 │ +2.85% │
│ AB12CD03  │ trading_usa │ Trading USA │ 389,186.85 │     +0.00 │      — │
│ AB12CD02  │ trading     │ Asesor      │ 104,176.22 │ +6,029.82 │ +1.13% │
│ AB12CD01  │ smart_cash  │ Smart Cash  │       0.00 │    +74.81 │ +4.25% │
└───────────┴─────────────┴─────────────┴────────────┴───────────┴────────┘
```

**Columnas:**
- **Legacy ID**: identificador de la cuenta que necesitas para `positions`, `orders`, `sync`.
- **Type**: `trading` (BMV), `trading_usa` (SIC fractional), `smart_cash` (fondo mercado de dinero).
- **Name**: alias que tú le pusiste en la app GBM+.
- **Value / P&L / P&L %**: pesos mexicanos.

---

### `gbm-mx positions`

Muestra la composición actual del portafolio para la cuenta de trading
principal (la primera de tipo `trading`).

```bash
gbm-mx positions
```

**Opciones:**
- `--legacy-id LEGACY_ID` — usar otra cuenta (e.g. `AB12CD02` si tienes
  múltiples estrategias).
- `--raw` — imprimir el JSON crudo en lugar de la tabla.

Output ejemplo (tabla, truncado):
```
                             Positions for AB12CD05
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┓
┃ Ticker     ┃    Qty ┃ Avg price ┃      Last ┃    Market ┃       P&L ┃ Weight ┃
┃            ┃        ┃           ┃           ┃     value ┃           ┃        ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━┩
│ AMD *      │    2.0 │  7,518.75 │  7,280.10 │ 14,560.19 │   -477.31 │  9.56% │
│ NAFTRAC    │    5.0 │     69.77 │     68.30 │    341.50 │     -7.35 │  0.22% │
│ ...        │    ... │       ... │       ... │       ... │       ... │    ... │
└────────────┴────────┴───────────┴───────────┴───────────┴───────────┴────────┘

Total portfolio value: 152,240.20 MXN
```

Cada fila es una posición real (los `Subtotal` de cada sección se filtran).

---

### `gbm-mx orders ls`

Lista órdenes **llenas** (estatus `Llena` / `gbmIntProcessStatus == 7`) en un
rango de fechas. Internamente itera día por día porque el backend de GBM no
acepta rangos.

```bash
gbm-mx orders ls --since 2026-04-01 --until 2026-05-19
```

**Opciones:**
- `--since YYYY-MM-DD` *(requerido)* — primer día del rango.
- `--until YYYY-MM-DD` — último día, default = hoy.
- `--legacy-id LEGACY_ID` — usar otra cuenta. Default: la primera de tipo trading.
- `--json` — output en JSON en lugar de tabla.

Output (tabla, truncado):
```
            Filled orders 2026-04-01 → 2026-05-19
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┓
┃ Date       ┃ Time     ┃ Ticker  ┃ Side ┃ Qty ┃  Price ┃ Amount  ┃ Comm. ┃ ID      ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━┩
│ 2026-04-08 │ 07:07:30 │ FMTY 14 │ BUY  │   4 │  15.12 │  60.48  │  0.15 │ 1071…83 │
│ 2026-04-14 │ 07:36:05 │ FNOVA 17│ BUY  │   1 │  38.47 │  38.47  │  0.10 │ 1074…51 │
│ ...        │      ... │     ... │  ... │ ... │    ... │    ...  │   ... │   ...   │
└────────────┴──────────┴─────────┴──────┴─────┴────────┴─────────┴───────┴─────────┘

77 filled orders
```

**Output JSON** (`--json`), útil para procesamiento downstream:
```bash
gbm-mx orders ls --since 2026-05-01 --json | jq '.[] | select(.issue_id == "WDC *")'
```

---

### `gbm-mx dividends ls`

Lista los movimientos en efectivo que GBM clasifica como dividendos en el
rango: dividendos en efectivo, reembolsos de capital, "resultado fiscal
distribuido" (de fondos), y las retenciones de ISR cedular correspondientes.

```bash
gbm-mx dividends ls --since 2026-01-01
```

**Opciones:**
- `--since YYYY-MM-DD` *(requerido)*
- `--until YYYY-MM-DD` — default: hoy.
- `--legacy-id LEGACY_ID` — otra cuenta. Default: trading principal.
- `--include-isr` / `--no-isr` — incluye o no las filas de ISR retenido.
  Default: incluidas.
- `--json` — salida JSON.

El pie de tabla resume **net received** (suma de abonos netos) y
**ISR withheld** (suma de retenciones).

```bash
# Solo los abonos que efectivamente entraron a la cuenta (sin ISR):
gbm-mx dividends ls --since 2026-01-01 --no-isr

# Export JSON:
gbm-mx dividends ls --since 2026-01-01 --json > divs.json
```

> ⚠️ Este endpoint vive en `api.appgbm.com` (no `api.gbm.com`). Si el
> backend rota su autorización podría empezar a devolver 401/403 antes
> que el resto de la lib — abre un issue si pasa.

---

### `gbm-mx sync`

El comando clave: **agrega filas nuevas a un `Portfolio.md`** sin tocar las
existentes. Deduplica por `ID de la orden`.

```bash
gbm-mx sync /ruta/a/Portfolio.md --since 2026-04-01
```

**Opciones:**
- `<PORTFOLIO_PATH>` *(posicional, requerido)* — ruta al `Portfolio.md`. Se
  crea si no existe.
- `--since YYYY-MM-DD` — primer día. Default: hace 60 días.
- `--until YYYY-MM-DD` — último día. Default: hoy.
- `--legacy-id LEGACY_ID` — otra cuenta. Default: trading principal.
- `--dry-run` — imprime las filas que escribiría sin tocar el archivo.

**Recomendación: siempre `--dry-run` la primera vez.**

```bash
gbm-mx sync ~/path/Portfolio.md --since 2026-04-01 --dry-run
```

Output:
```
Portfolio.md ya tiene 62 órdenes registradas.
Rango 2026-04-01 → 2026-05-19: 77 órdenes llenas, 15 nuevas.
--dry-run, no se escribe nada:

| 19 mayo 2026 | 07:08 a.m. | GFNORTE O | Compra | 2 | $184.98 MXN | $369.95 MXN | 0.25% | 0.92 MXN | Llena | 109298111 | EP47NC05 |
| 19 mayo 2026 | 07:08 a.m. | FMTY 14 | Compra | 10 | $14.55 MXN | $145.50 MXN | 0.25% | 0.36 MXN | Llena | 109298222 | EP47NC05 |
...
```

Si te gusta lo que ves, corre sin `--dry-run`.

**Formato exacto de las filas escritas** (compatible con `Portfolio.md`
preexistente):

```
| Fecha | Hora | Emisora | Tipo de operación | Titulos | Precio | Importe | Comisión | Monto de Comisión | Estatus de la orden | ID de la orden | Contrato |
```

- Fecha en español: `19 mayo 2026`.
- Hora 12h con punto: `07:08 a.m.`.
- Importe con `$` y `MXN`: `$369.95 MXN`.
- Monto de Comisión sin `$`: `0.92 MXN`.
- Comisión %: siempre `0.25%`.
- Estatus: siempre `Llena`.

**Diferencias normales** entre lo escrito y los correos viejos:
- El precio puede diferir centavos cuando una orden se llenó en varios ticks
  (el correo muestra precio del primer fill; el API devuelve el promedio
  ponderado).
- La comisión puede tener 1 centavo de diferencia por redondeo del IVA.

Ambos cambios son **mejoras** — el API tiene el precio efectivo correcto.

---

## Python API

Para usos programáticos (scripts, notebooks, integraciones).

### Login

```python
from gbm_mx_api import GbmClient

# Interactivo (pide TOTP por stdin)
client = GbmClient.login(
    email="...",
    password="...",
    totp_provider=lambda: input("TOTP: "),
)

# Sin persistir sesión:
client = GbmClient.login(
    email="...", password="...",
    totp_provider=lambda: "123456",
    persist_to=None,
)
```

### Reutilizar sesión guardada

```python
from gbm_mx_api import GbmClient

client = GbmClient.from_saved()  # devuelve None si no hay sesión válida
if client is None:
    # Aquí caes a interactive login
    ...
```

### Contracts + Accounts

```python
contracts = client.contracts.list()       # list[Contract]
main = client.contracts.get_main()        # Contract (el primero)

accounts = client.accounts.list(main.contract_id)        # list[Account]
trading = client.accounts.get_trading(main.contract_id)  # primer trading activo
```

`Account` trae directamente el P&L:
```python
print(f"{trading.name}: {trading.position.amount} MXN ({trading.plus_minus.amount:+,.2f})")
```

### Posiciones

```python
summary = client.positions.summary(trading.legacy_contract_id)

print(f"Total: {summary.total_market_value:,.2f}")
for p in summary.real_positions:           # excluye Subtotal
    print(f"  {p.issue_id} x{p.quantity}: P&L {p.yield_value:+,.2f}")

# Acceso por sección:
for p in summary.mercado_capitales:        # acciones BMV (incluye subtotales)
    print(p.issue_id, p.market_value)
for p in summary.mercados_globales_sic:    # USA
    ...
```

### Órdenes filled

```python
from datetime import date

filled = client.orders.list_filled(
    trading.legacy_contract_id,
    from_date=date(2026, 4, 1),
    to_date=date(2026, 5, 19),
)

# Cada FilledOrder es Pydantic v2 frozen:
for o in filled:
    print(o.sob_id, o.issue_id, o.side, o.quantity, o.average_price, o.commission)
    # o.amount = quantity * average_price (computed)
    # o.processed_at = datetime con timezone
```

Para órdenes raw de un día (incluyendo canceladas), `list_for_day`:

```python
day_orders = client.orders.list_for_day(
    trading.legacy_contract_id,
    date(2026, 5, 14),
)

for raw in day_orders:
    print(raw.sob_id, raw.status.name, raw.assigned_quantity, raw.cancel_quantity)
```

### Errores

Todas las excepciones heredan de `gbm_mx_api.GbmError`:

```python
from gbm_mx_api import (
    GbmError,         # base
    AuthError,        # 401/403
    ApiError,         # otros 4xx/5xx
    RateLimited,      # 429 (tiene .retry_after)
    TransportError,   # red / DNS / timeout
    MfaRequired,      # interno, no debería bubblear a usuarios de GbmClient.login
)
```

---

## Variables de entorno

| Variable | Uso |
|---|---|
| `GBM_EMAIL` | Email para login (alternativa a prompt). |
| `GBM_PASSWORD` | Password (idem). |
| `GBM_CLIENT_ID` | Override del client_id público (raro; default está hardcoded). |
| `GBM_LATITUDE`, `GBM_LONGITUDE` | Override de geolocalización (si no querés que ipapi.co detecte por IP). |
| `GBM_SESSION_PATH` | Override de la ruta del `session.json` (default: `~/.gbm-mx/session.json`). |

---

## Persistencia de sesión

- Archivo: `~/.gbm-mx/session.json` por default.
- Permisos: directorio `0700`, archivo `0600` (solo lectura/escritura para el dueño en POSIX).
- Write: atómico (escribe a `.tmp` y luego renombra).
- Contenido: tokens (access/identity/refresh), expiración, geo, client_id.
- Vida útil: `access_token` dura ~1h. La lib lo considera expirado 30s antes
  del tiempo real para evitar carreras.
- **No hay refresh automático** todavía. Cuando expira, `gbm-mx login` de
  nuevo.

> Si compartes una máquina, **borra `~/.gbm-mx/session.json`** al terminar:
> ```bash
> rm ~/.gbm-mx/session.json
> ```

---

## Troubleshooting

### "La latitud debe tener algún valor" (HTTP 400)

GBM exige headers `device-latitude` / `device-longitude`. La lib los manda
automáticamente. Si ves esto, probablemente:

- Estás llamando al endpoint directo con `curl` sin esos headers.
- El servicio de geolocalización IP cayó. Fija manualmente:
  ```bash
  export GBM_LATITUDE=19.4326
  export GBM_LONGITUDE=-99.1332
  gbm-mx login
  ```

### "Login failed: AuthError" después de cambiar password

Tu `session.json` viejo apunta al token de la sesión anterior. Bórralo:
```bash
rm ~/.gbm-mx/session.json
gbm-mx login
```

### "Código inválido (deben ser 6 dígitos numéricos)"

Asegúrate de:
1. Estar usando la app autenticadora correcta (Google Authenticator / Authy /
   la de tu OS).
2. Tu hora del sistema es correcta. TOTP depende de timestamp.
3. Estás copiando los 6 dígitos sin espacios.

### "Session is expired"

La sesión tiene ~1h de vida. Re-loguearse:
```bash
gbm-mx login
```

### El sync trae filas que no esperaba

Verifica con `gbm-mx orders ls --since X --json` para ver el data crudo de
`list_filled`. La lib filtra `gbmIntProcessStatus == 7` (Llena). Si una orden
tuviera otro status que también consideres "llena", abre un issue.

### Rate limit (HTTP 429)

GBM rara vez aplica rate limit a clientes web, pero si pasa:
- La lib respeta `Retry-After`.
- Para rangos grandes (90+ días), `list_filled` ya hace pausas de 0.5s cada
  10 días.
- Si igual cae 429, espera unos minutos.

### Diferencias de precio vs los correos de GBM

Es esperado en órdenes que se llenan en múltiples ticks. El **API devuelve el
precio promedio ponderado** (correcto), los correos a veces muestran el
precio del primer fill (no representativo). Confía en lo que escribe la lib.

### El archivo `Portfolio.md` se generó con encoding raro

La lib siempre escribe en UTF-8. Si tu editor lo muestra mal, revisa la
config del editor. En la línea de comandos:
```bash
file Portfolio.md   # debe decir "UTF-8 Unicode text"
```
