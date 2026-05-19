# Fase 0 — Plan de descubrimiento de endpoints

Objetivo: catalogar los endpoints reales del backend de GBM+ antes de escribir
código. Se hace una sola vez (puede repetirse si GBM cambia algo).

## Preparación

1. Loguearse en **`https://homebroker-pro.gbm.com`** (recomendado, es la app
   web más completa). Alternativa: `https://gbm.com` → "Acceso clientes".
2. Abrir **DevTools** (Cmd+Opt+I en Mac, Chrome/Edge/Brave).
3. Ir a la pestaña **Network**.
4. Activar el filtro **Fetch/XHR** (oculta CSS, imágenes, fonts).
5. Marcar **Preserve log** (no se borra al navegar).
6. (Opcional) Botón "Disable cache" activado.

## Qué capturar — por sección de la app

Para cada sección de la lista, hacer la acción descrita y capturar **todos los
requests** que aparezcan en Network. Para cada request anotar en
`02-endpoints-discovered.md`:

- **URL completa** (sin tokens, sin IDs personales).
- **Método** (GET/POST).
- **Request payload** (Body o Query string).
- **Response** (estructura — basta con copiar campos top-level y un ejemplo).
- **Headers relevantes** (sólo los no obvios: `x-client-id`, `x-something`).

> Tip rápido: en DevTools, click derecho sobre un request → **Copy as cURL**.
> Pegar en un archivo y limpiar token/cookies después.

### Bloque A — Autenticación

- [ ] Hacer **logout** y **login** de nuevo.
- Capturar: el POST de login, qué devuelve (token, expiración, refresh token
  si existe), y cualquier llamada inmediata post-login (bootstrap, contracts,
  perfil de usuario).

### Bloque B — Cuentas y posiciones

- [ ] Entrar a **"Mi portafolio"** / **"Posiciones"**.
- Capturar: cómo se obtiene la lista de posiciones, valor de mercado actual,
  PnL no realizado.
- [ ] Cambiar entre estrategias / cuentas si tienes más de una.
- [ ] Ver detalle de una posición individual (click sobre un ticker).

### Bloque C — Histórico de órdenes ⭐

Este es el bloque crítico — es lo que reemplaza el parsing de correos.

- [ ] Entrar a **"Órdenes"** / **"Operaciones"** / **"Historial"**.
- [ ] Filtrar por **fecha** (último mes, últimos 3 meses, rango custom).
- [ ] Filtrar por **estatus** (Llena, Cancelada, etc.).
- [ ] Cambiar de página si hay paginación.
- [ ] Click en una orden individual para ver detalle.
- Anotar especialmente: ¿el endpoint acepta `from_date`/`to_date`? ¿cómo se
  ven los campos `price`, `quantity`, `status`, `id`, `fill_time`, `commission`?

### Bloque D — Movimientos de efectivo

- [ ] Entrar a **"Estado de cuenta"** / **"Movimientos"**.
- [ ] Capturar movimientos: depósitos, retiros, liquidaciones, comisiones,
  dividendos, ISR retenido.
- [ ] Exportar a Excel/PDF si la opción existe (ver si dispara un endpoint).

### Bloque E — Estados de cuenta mensuales

- [ ] **"Estados de cuenta"** / **"Documentos fiscales"**.
- [ ] Descargar el estado del mes anterior.
- Anotar: ¿es un endpoint que devuelve PDF directo? ¿requiere token aparte?

### Bloque F — Constancia fiscal anual

- [ ] **"Constancias"** / **"Información fiscal"**.
- [ ] Descargar la constancia del año anterior.

### Bloque G — Cotizaciones / Market data

- [ ] Ir al detalle de un ticker (ej. **NAFTRAC**, **AMD**, **WALMEX**).
- [ ] Ver gráfica intradia.
- [ ] Cambiar timeframe (1D, 1W, 1M, 1Y).
- [ ] Si hay book/profundidad de mercado, abrirlo.

### Bloque H — Catálogo de instrumentos

- [ ] Usar la **búsqueda de instrumentos** (typeahead).
- [ ] Buscar varios: un IPC mexicano, un SIC (americano vía SIC), un FIBRA, un ETF.

### Bloque I — Colocar una orden (sin enviarla)

- [ ] Abrir el modal de **"Comprar"** sin completar.
- [ ] Capturar los endpoints de validación / preview / fees que se disparan
      antes de enviar.
- ⚠️ **No enviar la orden real** si no quieres ejecutarla. Cancelar el modal.

## Forma de entregar la captura

Opciones, de menor a mayor esfuerzo:

1. **Export HAR**: en DevTools → pestaña Network → botón ⬇ "Export HAR". Crea
   un archivo `.har` con todos los requests/responses de la sesión. Lo guardas
   en `<repo>/discovery/<fecha>.har` (este folder está en `.gitignore`).
   Yo lo proceso después y extraigo lo relevante.
   - ⚠️ El HAR puede contener tu token. Antes de subir al repo, redactar el
     header `Authorization` con un find/replace.
2. **Copy as cURL** request por request, pegar en un archivo de texto. Más
   tedioso pero más controlado sobre qué se comparte.
3. **Screenshots + descripción** de DevTools. Última opción.

## Higiene de privacidad

- **Nunca subir al repo**: tokens, cookies, IDs de cuenta, número de contrato,
  RFC, CURP, IDs de orden con tu nombre, montos personales, holdings reales.
- **Sí se puede subir** al repo (público): forma del endpoint, nombres de
  campos, tipos de datos, ejemplos sintéticos con valores ficticios.
- El folder `discovery/` va en `.gitignore` — solo material destilado y
  anonimizado pasa a `02-endpoints-discovered.md`.

## Tiempo estimado

- Bloques A-D: 20-30 min (lo más importante).
- Bloques E-I: 30-40 min (lo opcional / futuro).
- Total: ~1 hora si quieres todo, 30 min si solo el camino crítico (A+C+D).

## Después del descubrimiento

Con `02-endpoints-discovered.md` lleno, regresamos a la decisión de alcance
con horas reales — no estimaciones a ciegas — y arrancamos código.
