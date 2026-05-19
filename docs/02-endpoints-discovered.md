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

## Pendientes por probar

| Endpoint | Estado | Notas |
|---|---|---|
| Refresh token | No probado | `POST /api/v1/session/user/refresh` con `{refreshToken}` |
| Cancelar orden | No probado | `POST /GBMP/api/Operation/CancelCapitalOrder` |
| Movimientos de efectivo | Conocido (gbmplus) | `GET /v1/contracts/{main}/accounts/{id}/cash-transactions` |
| Estado de cuenta PDF | No descubierto | Probable: `/v1/contracts/.../statements` |
| Catálogo BMV | No descubierto | Análogo a `getMarketsUSA` |
| Cotizaciones / market data | No descubierto | Probablemente en `homebroker-api` |
| Constancia fiscal | No descubierto | |
| Otros valores de `gbmIntProcessStatus` | No descubierto | Necesita más muestras de órdenes |
| Comportamiento de `bitBuy: false` (Venta) | No validado | |
