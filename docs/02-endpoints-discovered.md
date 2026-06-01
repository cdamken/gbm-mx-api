# Endpoints descubiertos — GBM+

Resultados de la Fase 0 (sesión de descubrimiento del 2026-05-18).
Todos los ejemplos usan valores **sintéticos** o anonimizados.

## Stack confirmado

GBM usa **AWS Cognito (`us-east-1`, pool `us-east-1_BKu7qAohu`)** detrás de
`auth.gbm.com`. El JWT devuelto por el step 2 del login confirma esto en su
campo `iss`. El `client_id` real de Cognito (visible en el JWT como `aud`)
no se usa directamente — el cliente público va contra el wrapper de GBM.

## Tres backends

| Host | Protocolo | Auth |
|---|---|---|
| `auth.gbm.com/api/v1/...` | REST/JSON | Sin token (solo para login). Requiere headers `device-latitude/device-longitude`. |
| `api.gbm.com/v1,v2/...` | REST/JSON | `Authorization: Bearer <accessToken>` + headers geo. |
| `homebroker-api.gbm.com/GBMP/api/...` | RPC sobre JSON (payload `{"request": ...}`) | `Authorization: Bearer <accessToken>` + headers geo. |

## Autenticación — flow completo

### Headers obligatorios en TODAS las requests

```
device-latitude: <float>     # ej. 19.4326
device-longitude: <float>    # ej. -99.1332
```

Son anti-fraude. Sin estos headers, `auth.gbm.com` rechaza con 400
`"La latitud debe tener algún valor."` antes de validar credenciales.

### Step 1 — login inicial

```
POST https://auth.gbm.com/api/v1/session/user
Headers:
  Content-Type: application/json
  device-latitude: 19.4326
  device-longitude: -99.1332
Body:
  {
    "clientid": "7c464570619a417080b300076e163289",
    "user": "<email>",
    "password": "<password>"
  }
```

**`clientid` es público** (sale en URL `auth.gbm.com/signin?client_id=...`).
Es el ID de la app web pública de GBM.

**Response 200** cuando hay 2FA habilitado:
```json
{
  "challengeInfo": {
    "challengeType": "SOFTWARE_TOKEN_MFA",
    "session": "<token de sesión temporal Cognito>",
    "user": "<user id Cognito>",
    "timestamp": 1779120524467
  },
  "authorizedUserDevice": false,
  "authorizedUserDeviceHistory": true,
  "code": 2,
  "id": "ChallengeRequired",
  "message": "El usuario debe verificar su identidad."
}
```

### Step 2 — responder al challenge MFA TOTP

```
POST https://auth.gbm.com/api/v1/session/user/challenge
Headers:    (mismos que Step 1, incluyendo geo)
Body:
  {
    "clientid": "7c464570619a417080b300076e163289",
    "user": "<user del step 1>",
    "session": "<session del step 1>",
    "code": "<código TOTP de 6 dígitos>",
    "challengeType": "SOFTWARE_TOKEN_MFA"
  }
```

**Response 200**:
```json
{
  "signInRedirect": "https://www.appgbm.com/",
  "accessToken": "<JWT, válido 3600s>",
  "identityToken": "<JWT con claims del usuario>",
  "refreshToken": "<token de refresh>",
  "tokenType": "Bearer",
  "expiresIn": 3600,
  "code": 0,
  "id": "Success",
  "message": "Exitoso"
}
```

### Identity token (JWT) — claims útiles

El `identityToken` decodificado trae (entre otros):
- `sub`: UUID del usuario en Cognito
- `cognito:username`: otro UUID interno
- `custom:legacy_id`: ID interno legacy del usuario en sistemas viejos
- `email`, `email_verified`, `Company`: "GBM"
- `auth_time`, `exp`, `iat`: timestamps Unix
- `iss`: `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_BKu7qAohu`

### Refresh token (NO probado todavía)

El `refreshToken` viene en la respuesta pero no se ha descubierto el
endpoint para usarlo. Hipótesis: similar a Cognito directo
(`POST /api/v1/session/user/refresh` con `{refreshToken}`). Pendiente.

---

## Endpoint: `GET /v1/contracts`

```
GET https://api.gbm.com/v1/contracts
Authorization: Bearer <accessToken>
```

**Response**:
```json
[
  {
    "contract_id": "<UUID>",
    "first_name": "<nombre>",
    "middle_name": "<apellido paterno>",
    "last_name": "<apellido materno>",
    "legacy_contract_id": "<ID legacy general, ej. EP47NC>",
    "contract_status": "active",
    "opening_type": "long_opening",
    "is_legacy": false,
    "is_migrated": false,
    "is_dashboard_blocked": false,
    "created_at": "2026-01-07T15:59:31.077165+00:00"
  }
]
```

⚠️ El `legacy_contract_id` aquí es el del **contrato general** (sin sufijo
de cuenta). Para llamadas al backend legacy hay que usar el de la cuenta
específica (ver `/accounts`).

---

## Endpoint: `GET /v2/contracts/{contract_id}/accounts`

```
GET https://api.gbm.com/v2/contracts/<UUID>/accounts
Authorization: Bearer <accessToken>
```

**Response**:
```json
[
  {
    "account_id": "<UUID>",
    "legacy_contract_id": "<ID legacy con sufijo de cuenta, ej. EP47NC05>",
    "name": "<alias dado por el usuario>",
    "number": 5,
    "management_type_template": "trading",
    "position": {"amount": 151536.95, "currency": "MXN"},
    "plus_minus": {"amount": 3292.88, "currency": "MXN"},
    "plus_minus_percentage": 0.0285,
    "status": "active",
    "collecting_account": "<CLABE>",
    "profile_type": "not_applicable",
    "created_at": "2026-04-01T17:24:42.178542+00:00"
  }
]
```

**`management_type_template` posibles**:
- `trading` — cuenta de bolsa MX (BMV)
- `trading_usa` — fractional shares USA
- `smart_cash` — fondo mercado de dinero

Ya da **P&L de cada estrategia** en `plus_minus`. Útil para
`PnL-Evolucion.md`.

---

## Endpoint: `POST /GBMP/api/Portfolio/GetPositionSummary` ⭐

```
POST https://homebroker-api.gbm.com/GBMP/api/Portfolio/GetPositionSummary
Authorization: Bearer <accessToken>
Body: {"request": "<legacy_contract_id con sufijo, ej. EP47NC05>"}
```

**Response** (composición del portafolio en 5 secciones):

```json
{
  "mercadosGlobalesSIC": [          // acciones USA (vía SIC)
    {
      "positionValueType": 0,
      "issueId": "AMD *",
      "issueName": "ADVANCED MICRO DEVICES INC.",
      "instrumentType": 2,
      "quantity": 2.0,
      "averagePrice": 7518.75,
      "lastPrice": 7272.55,
      "closePrice": 7357.16,
      "yieldValue": -492.4,
      "marketValue": 14545.1,
      "dailyVariationPercentage": -0.0115,
      "historicalVariationPercentage": -0.0327,
      "averageCost": 15037.5,
      "positionPercentage": 0.0961
    },
    {"issueId": "Subtotal", ...}
  ],
  "mercadoCapitales": [...],          // acciones BMV (IPC y demás)
  "sociedadesInversionDeuda": [...],  // fondos (GBMF2 BF, etc.)
  "efectivo": [
    {"issueId": "EFEC.  MISMO DIA", ...},
    {"issueId": "EFEC. 24 HRS.", ...},
    {"issueId": "EFEC. 48 HRS.", ...},
    {"issueId": "EFEC. MAYOR 48 HRS.", ...},
    {"issueId": "Subtotal", ...}
  ],
  "totalPortfolioValue": [
    {"issueId": "Valor total de la cartera", "marketValue": <total>, ...}
  ]
}
```

**`positionValueType`**: `0`=SIC, `1`=BMV, `5`=Deuda, `27`=Efectivo, `1000`=Total.

Reemplaza al `.xlsx` "Detalle Portafolio".

---

## Endpoint: `POST /GBMP/api/Operation/GetBlotterOrders` ⭐⭐

**Clave para reemplazar el flujo de correos `.eml`.**

```
POST https://homebroker-api.gbm.com/GBMP/api/Operation/GetBlotterOrders
Authorization: Bearer <accessToken>
Body:
  {
    "contractId": "<legacy_contract_id de la cuenta, ej. EP47NC05>",
    "instrumentTypes": [0, 2],
    "processDate": "2026-05-14T06:00:00Z"
  }
```

### Comportamiento descubierto

| Variante | Resultado |
|---|---|
| `processDate` con fecha pasada | ✅ Devuelve las órdenes de ese día |
| Sin `processDate` | Devuelve las del día actual |
| Con `fromDate`/`toDate` (rango) | Backend acepta pero devuelve solo el default → **rango NO funciona** |

Para histórico hay que **iterar día por día**. `gbmplus` hardcodeaba a
hoy — eso ya no es limitación.

`instrumentTypes`: `[0, 2]` = IPC (BMV) + SIC (USA). Probablemente
podríamos pedir más subtipos, no se han mapeado todos.

### Response shape

```json
{
  "getRealTimePosition": {...},
  "ordersList": [
    {
      "accountId": "EP47NC05",
      "algoTradingTypeId": <int>,
      "assignedQuantity": 1,
      "averagePrice": 8692.24,
      "bitBuy": true,
      "cancelMessage": "",
      "cancelQuantity": 0,
      "capitalOrderTypeId": 1,
      "commision": 21.73,
      "duration": <int>,
      "gbmIntProcessStatus": 7,
      "instrumentType": 2,
      "isCancelable": false,
      "issueId": "WDC *",
      "iva": 3.48,
      "mainOrderAMId": 0,
      "maxFloor": <int>,
      "minQty": <int>,
      "originalQuantity": 1,
      "pegOffsetValue": <int>,
      "predespachador": false,
      "preorderId": 0,
      "price": 8692.24,
      "processDate": "2026-05-14T08:30:49.64-06:00",
      "sobId": 109142599,
      "stopPrice": 0,
      "treasuryOrderTypeId": <int>,
      "triggerPrice": 0,
      "vigencia": "<string>",
      "vigenciaId": <int>
    }
  ]
}
```

### Enums descubiertos

- **`gbmIntProcessStatus`**:
  - `5` → Cancelada
  - `7` → **Llena** (la que nos interesa para `Portfolio.md`)
  - Otros valores no descubiertos aún (parcialmente llena, pendiente, etc.)
- **`bitBuy`**: `true` = Compra, `false` = Venta (asumido, no validado con venta real)
- **`instrumentType`**: `0` = IPC, `2` = SIC (matching `instrumentTypes` del request)
- **`capitalOrderTypeId`**: `1` (no observados otros valores)

### Mapping a columnas de `Portfolio.md`

| Columna | Campo blotter | Notas |
|---|---|---|
| Fecha | `processDate[:10]` parseado | ISO 8601 con TZ -06:00 (CDMX) |
| Hora | `processDate[11:]` parseado | Convertir a `HH:MM a.m./p.m.` |
| Emisora | `issueId` | Coincide exacto |
| Tipo de operación | `bitBuy ? "Compra" : "Venta"` | |
| Titulos | `assignedQuantity` | NO `originalQuantity` |
| Precio | `averagePrice` | |
| Importe | `assignedQuantity * averagePrice` | Calcular |
| Comisión | hardcoded `0.25%` | No hay campo — es config de la cuenta |
| Monto de Comisión | `commision` | |
| Estatus de la orden | `gbmIntProcessStatus == 7 ? "Llena" : ...` | Filtrar |
| ID de la orden | `sobId` | int, 9 dígitos, coincide con los correos |
| Contrato | `accountId` | Ej. `EP47NC05` |

### Validación cruzada (14 mayo 2026)

- Blotter devolvió 8 órdenes.
- `Portfolio.md` tenía 5 transacciones ese día.
- Las 5 con `gbmIntProcessStatus == 7` coinciden 100% con `Portfolio.md`.
- Las 3 con status=5 son canceladas (correctamente ausentes de `Portfolio.md`).

---

## Endpoint: `GET /v2/trading/contracts/{contract_id}/transactions` ⭐ (api.appgbm.com)

Descubierto 2026-05-22 husmeando la pestaña "Dividendos" en
`https://www.appgbm.com/trading/MEX/{LEGACY_ID}` con DevTools. **El host
es diferente al resto** (`api.appgbm.com` vs `api.gbm.com` /
`homebroker-api.gbm.com`).

### Request

```
GET https://api.appgbm.com/v2/trading/contracts/{contract_id}/transactions
    ?page=1
    &page_size=100
    &start_date=2026-01-01
    &end_date=2026-05-22
    &transac_type=dividend
    &legacy_contracts_id=EP47NC05
```

- **`contract_id`** — UUID del contrato (no el legacy ID).
- **`legacy_contracts_id`** — sí, plural; sigue siendo el legacy ID típico
  (`EP47NC05`). El backend hace joins por ambos.
- **`transac_type=dividend`** — filtro de tipo. Cuando se manda, devuelve
  todos los movimientos en efectivo que GBM clasifica como dividendos:
  - `Abono Efectivo Dividendo, Cust. Normal` (dividendo en efectivo).
  - `Abono Reembolso de Capital, Cust. Normal` (devolución de capital,
    no tributable como dividendo en MX).
  - `Abono Efectivo Resultado Fiscal Distribuido` (fondos que distribuyen
    su utilidad fiscal).
  - `ISR Cedular por Dividendos` — las retenciones que GBM ya pagó al SAT.

### Response

```json
{
  "items": [
    {
      "transaction_id": 24286814,
      "contract_id": "87e24157-…",
      "legacy_contract_id": "EP47NC05",
      "security_id": "FMX 23",
      "security_name": "Fibra Infraestructura y Energía México,",
      "transaction_type": "prestamo_valores",
      "sub_transaction_type": 266,
      "transaction_amount": 14.3604,
      "transaction_net_amount": 14.3604,
      "transaction_commission": 0.0,
      "transaction_tax": 0.0,
      "process_date": "2026-05-21T12:54:36+00:00",
      "settlement_date": "2026-05-21T06:00:00+00:00",
      "transaction_time": "06:54:36",
      "transaction_description": "Abono Reembolso de Capital, Cust. Normal"
    }
  ],
  "pagination_metadata": {
    "total_items": 12,
    "page_count": 10,
    "previous": "",
    "next": "?page=2&…",
    "page_size": 10,
    "page": 1
  }
}
```

Notas:
- El campo `transaction_type` casi siempre dice `"prestamo_valores"`, aunque
  el movimiento sea claramente un dividendo. **No es un buen discriminador**;
  usa `transaction_description`.
- `is_withholding` en el modelo Pydantic detecta los ISR con regex sobre
  la descripción.
- Autorización: el mismo Bearer token de Cognito que `api.gbm.com` (probado
  empíricamente; ambos comparten user pool aunque tengan client_id propio
  por host).

### Mapeo a UI

| Columna "Dividendos" del web app | Campo de la respuesta |
|---|---|
| Fecha | `process_date` (toma la parte de fecha) |
| Hora | `transaction_time` |
| Emisora | `security_id` |
| Descripción | `transaction_description` |
| Monto | `transaction_amount` (bruto) — el net suele ser igual |

---

## Pendientes por probar

| Endpoint | Estado | Notas |
|---|---|---|
| Refresh token | No probado | `POST /api/v1/session/user/refresh` con `{refreshToken}` |
| Cancelar orden | No probado | `POST /GBMP/api/Operation/CancelCapitalOrder` |
| Movimientos de efectivo (otros tipos) | Parcial | `?transac_type=deposit\|transfer_in\|transfer_out` ya conocidos por gbmplus; los demás (`buy`, `sell`, fees) por descubrir |
| Estado de cuenta PDF | No descubierto | Probable: `/v1/contracts/.../statements` |
| Catálogo BMV | No descubierto | Análogo a `getMarketsUSA` |
| Cotizaciones / market data | No descubierto | Probablemente en `homebroker-api` |
| Constancia fiscal | No descubierto | |
| Otros valores de `gbmIntProcessStatus` | No descubierto | Necesita más muestras de órdenes |
| Comportamiento de `bitBuy: false` (Venta) | No validado | |

---

## Endpoints del web app `appgbm.com` (descubiertos 2026-06-01 vía DevTools)

El web app moderno en `https://www.appgbm.com/` usa endpoints específicos
del dashboard que **no están expuestos** por `api.gbm.com/v2/contracts/{id}/accounts`.
Para mantener paridad con lo que ve el usuario en la app móvil/web hay que
mapear estos.

### `GET /v1/dashboard/contracts/{contract_uuid}/accounts`

Host: `api.appgbm.com`. **Devuelve 5 cuentas** (las 4 del endpoint legacy
+ una oculta de tipo `wealth` que es **Smart Cash Dólares**).

```json
{
  "data": [
    {
      "account_id": "...uuid...",
      "management_type_template": "trading"      // BMV (Personal, Asesor)
                                | "trading_usa"  // Trading USA (fractional)
                                | "smart_cash"   // Smart Cash MXN
                                | "wealth",      // Smart Cash USD (oculto en v2)
      "name": "Personal" | "Smart Cash Dólares" | …,
      "number": 1..5,
      "legacy_contract_id": "EP47NC01..05",
      "status": "active",
      "collecting_account": "601180400…",
      "created_at": "2026-01-07T15:59:37.250529Z",
      "is_smart_cash_usd": false | true
    }
  ]
}
```

**Diferencia clave vs `api.gbm.com/v2/contracts/{id}/accounts`:**

- El v2 legacy devuelve 4 cuentas (omite la de tipo `wealth`).
- El dashboard devuelve 5, incluyendo Smart Cash Dólares con
  `is_smart_cash_usd: true`.
- El dashboard **NO** trae `position.amount` ni `plus_minus` — solo
  metadata. Para balances hay que combinar con `/v2/` legacy o con
  `GetPositionSummary`.

### `GET /v1/dashboard/contracts/{contract_uuid}/investments-groups/smart_cash/accounts`

Host: `api.appgbm.com`. Endpoint específico para Smart Cash (probable
balance + holdings). **Visto en performance.getEntriesByType pero no
cacheado** — su response no quedó accesible desde JS en el momento de
discovery. Por descubrir.

### `GET /v1/dashboard/parties/{party_uuid}`

Host: `api.appgbm.com`. Devuelve datos personales del titular (nombre,
fecha nac., estado civil, `investment_profile`, `risk_type`). El
`party_uuid` es nuevo — distinto al `contract_uuid` y al `legacy_contract_id`.

### `GET /v1/dashboard/contracts/{contract_uuid}/parties/{party_uuid}/sunset/{email}`

Host: `api.appgbm.com`. Status de migración entre apps:
`{ "default_app": "AE", "has_gbm_access": false, "show_migration_warning": false, … }`.

### "Total Invertido" se calcula del lado del cliente

El número grande "TOTAL INVERTIDO" que muestra la app móvil/web **no
viene de un endpoint** — se calcula client-side sumando los balances de
las 5 cuentas. Verificado leyendo `localStorage` / `sessionStorage` del
web app: no hay ningún string que contenga el valor total cacheado.
Esto significa que **no hay nada que añadir a la librería** para
reproducir ese número: ya lo calculamos igual sumando `account.position.amount`.
La diferencia observada con la app móvil (~$1,000 sobre ~$800K) es
**drift intradía**: USD/MXN y precios SIC/USA moviéndose entre el
momento de nuestro fetch y el momento que la app móvil hace su llamada
live.

### Reverse-engineering protocol (para sesiones futuras)

Para capturar nuevos endpoints del web app sin proxy:

1. Abrir `https://www.appgbm.com/` logueado.
2. DevTools → Console → ejecutar:
   ```js
   performance.getEntriesByType('resource')
     .filter(e => /api\.(app)?gbm/i.test(e.name))
     .map(e => e.name);
   ```
3. Para responses cacheados:
   ```js
   const all = {};
   for (const k of Object.keys(sessionStorage)) {
     if (k.startsWith('gbm-cache-')) all[k.replace('gbm-cache-','')] = JSON.parse(sessionStorage[k]);
   }
   ```
4. Para endpoints que no se cachean: instalar un interceptor de
   `fetch` y `XMLHttpRequest.send` que vuelque a `window.__captured`,
   navegar la SPA para forzar la request, leer `__captured`.
   La fetch CORS-cross-origin desde DevTools console **falla** sin el
   Bearer token de la app, así que NO se puede hacer `fetch(url)` a
   mano — hay que pasar por los interceptors.
