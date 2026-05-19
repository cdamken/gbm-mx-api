# experiments/

Scripts de prueba de conectividad contra el backend de GBM. **Todo este folder
está en `.gitignore`** — incluye credenciales y posiblemente capturas con datos
personales.

## Setup

```bash
cd gbm-mx-api/experiments

# Crear .env desde la plantilla
cp .env.example .env
# Editar .env con tus datos
$EDITOR .env

# (Opcional) Entorno virtual para no contaminar Python global
python3 -m venv .venv
source .venv/bin/activate

# Solo requiere requests (sin gbmplus)
pip install requests
```

## Qué necesitas

| Variable | Valor |
|---|---|
| `GBM_EMAIL` | El email con el que entras a GBM+ |
| `GBM_PASSWORD` | Tu contraseña |
| `GBM_CLIENT_ID` | Ya pre-cargado en el script (es público — `7c464570619a417080b300076e163289`) |

El **código TOTP** de la app de 2FA se pide interactivo cada vez que corres
un script. **No se guarda nunca.**

## Scripts (en orden de ejecución)

1. **`01_test_login.py`** — solo intenta autenticarse. Imprime la respuesta
   cruda del backend (redactando tokens) para que veamos cómo es el flow de
   2FA real. Output → `outputs/01_login_response.json` (gitignored).

2. **`02_test_endpoints.py`** — *(se escribe después del paso 1)* — usa el
   token del login y prueba los endpoints conocidos: cuentas, posiciones,
   blotter de órdenes.

## Privacidad

- `.env` está en `.gitignore`. **Nunca commit.**
- `outputs/` también está en `.gitignore`. Las respuestas pueden traer IDs
  reales, holdings, etc.
- Los scripts **redactan** automáticamente: tokens, contraseñas y campos
  marcados como sensibles antes de imprimir a consola.
- Si compartes output con alguien, usa los archivos en `outputs/redacted/`
  que generan los scripts (anonimización adicional).
