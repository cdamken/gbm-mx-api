# Guía para contribuir

Cómo desarrollar `gbm-mx-api` localmente: setup, estructura del código,
estándares de calidad, cómo agregar un endpoint nuevo.

## Setup

```bash
git clone https://github.com/cdamken/gbm-mx-api.git
cd gbm-mx-api

python3 -m venv .venv
.venv/bin/pip install -e ".[dev,cli]"

# Verificar que todo pasa
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src
.venv/bin/python -m pytest -q
```

Requisitos:
- Python 3.10+
- Acceso a internet para que `pip install` jale `httpx`, `pydantic`, `typer`, `rich`.

No requiere credenciales de GBM para correr los tests — todo está mockeado con
`respx`.

## Estructura del paquete

```
src/gbm_mx_api/
├── __init__.py        # re-exports públicos (lo que el usuario importa)
├── _version.py        # __version__ — single source of truth
├── py.typed           # marker PEP 561: el paquete trae tipos
├── errors.py          # jerarquía de excepciones
├── client.py          # GbmClient facade
├── auth/              # autenticación
│   ├── login.py       # start_login + complete_mfa + login() top-level
│   └── session.py     # Session model + persistencia
├── transport/         # HTTP layer
│   ├── http.py        # HttpClient con retries, redacción, geo
│   └── redaction.py   # helpers para no leakear secrets en logs
├── domain/            # modelos Pydantic v2 (sin I/O, solo data)
│   ├── enums.py       # OrderStatus, Side, InstrumentType, ...
│   ├── contract.py    # Contract
│   ├── account.py     # Account, Money
│   ├── order.py       # Order (raw blotter) + FilledOrder (proyección)
│   └── position.py    # Position + PortfolioSummary
├── api/               # módulos por recurso de GBM
│   ├── _base.py       # ApiBase compartido (lleva el HttpClient)
│   ├── contracts.py   # GET /v1/contracts
│   ├── accounts.py    # GET /v2/contracts/{id}/accounts
│   ├── positions.py   # POST /GBMP/Portfolio/GetPositionSummary
│   └── orders.py      # POST /GBMP/Operation/GetBlotterOrders
└── cli/               # Typer entry point
    ├── __main__.py    # commands: login, accounts, positions, orders, sync
    ├── _common.py     # get_client() y helpers
    └── _portfolio_md.py  # writer del formato Portfolio.md
```

Convención clave: **un módulo `api/*.py` por endpoint conceptual**, cada uno
con su clase que hereda de `ApiBase` y se enchufa al `GbmClient`.

## Layers (responsabilidades)

```
┌─────────────────────────────────────────────────────────┐
│ cli/         — UX, prompts, format de salida (Rich)     │
├─────────────────────────────────────────────────────────┤
│ client.py    — facade público, holds HttpClient         │
├─────────────────────────────────────────────────────────┤
│ api/         — un módulo por recurso, devuelve domain/  │
├─────────────────────────────────────────────────────────┤
│ domain/      — modelos puros (Pydantic), sin I/O        │
├─────────────────────────────────────────────────────────┤
│ transport/   — único punto que toca la red              │
├─────────────────────────────────────────────────────────┤
│ auth/        — login + sesión (cruza transport)         │
└─────────────────────────────────────────────────────────┘
```

Reglas:
- **`domain/` no importa nada de `transport/` ni `api/`** — modelos puros.
- **`api/*` no toca `httpx` directamente** — usa `self._http` (el `HttpClient`).
- **`cli/` no llama endpoints crudos** — pasa por `GbmClient`.

## Estándares de calidad

Todo lo siguiente debe pasar antes de un PR / merge:

```bash
.venv/bin/ruff check src tests           # lint
.venv/bin/ruff format --check src tests  # formatting
.venv/bin/mypy src                       # types (strict mode)
.venv/bin/python -m pytest -q            # tests
```

Hooks recomendados (opcional, no obligatorio):
```bash
# .git/hooks/pre-commit
#!/bin/sh
cd "$(git rev-parse --show-toplevel)"
.venv/bin/ruff check src tests || exit 1
.venv/bin/ruff format --check src tests || exit 1
.venv/bin/mypy src || exit 1
.venv/bin/python -m pytest -q || exit 1
```

## Tests

- **`pytest` + `respx`** para mockear `httpx`.
- Cero red real en tests. La sesión se construye con `Session(...)` directamente.
- Fixtures grabadas en `tests/fixtures.py` con shapes reales (anonimizados).

Para correr un test específico:
```bash
.venv/bin/python -m pytest tests/test_orders.py::test_orders_list_filled_filters_and_sorts -v
```

Cobertura mínima esperada: cada `api/*` con al menos 1 test happy path + 1
test de error.

## Cómo agregar un endpoint nuevo

Ejemplo: agregar `GET /v1/contracts/{main}/accounts/{id}/cash-transactions`.

### 1. Modelo de dominio

`src/gbm_mx_api/domain/cash_transaction.py`:
```python
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class CashTransaction(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")
    transaction_id: str = Field(alias="transactionId")
    amount: Decimal
    currency: str = "MXN"
    type: str
    settled_at: datetime = Field(alias="settledAt")
```

Re-exportar en `domain/__init__.py`.

### 2. API module

`src/gbm_mx_api/api/cash_transactions.py`:
```python
from gbm_mx_api.api._base import ApiBase
from gbm_mx_api.domain.cash_transaction import CashTransaction

class CashTransactions(ApiBase):
    def list(self, contract_id: str, account_id: str, *, page: int = 0, page_size: int = 50) -> list[CashTransaction]:
        url = f"https://api.gbm.com/v1/contracts/{contract_id}/accounts/{account_id}/cash-transactions"
        body = self._http.get(url, params={"page": page, "page_size": page_size})
        return [CashTransaction.model_validate(item) for item in body]
```

### 3. Cablearlo en el client

`src/gbm_mx_api/client.py`:
```python
from gbm_mx_api.api.cash_transactions import CashTransactions
# ...
class GbmClient:
    def __init__(self, session):
        # ...
        self.cash_transactions = CashTransactions(self._http)
```

### 4. Tests con respx

`tests/test_cash_transactions.py`:
```python
@respx.mock
def test_cash_transactions_list(http):
    respx.get(...).mock(return_value=httpx.Response(200, json=[...]))
    out = CashTransactions(http).list("contract-id", "account-id")
    assert len(out) == 2
```

### 5. (Opcional) CLI subcomando

`cli/__main__.py`:
```python
cash_app = typer.Typer(...)
app.add_typer(cash_app, name="cash")

@cash_app.command("ls")
def cash_ls(...):
    with get_client(session_path) as client:
        txs = client.cash_transactions.list(...)
    # render tabla con Rich
```

### 6. Documentar

- Update `docs/02-endpoints-discovered.md` con la forma del request/response.
- Update `docs/03-usage.md` con ejemplo de uso.
- Update `CHANGELOG.md`.

## Privacidad — reglas para contribuidores

**Nunca commitar:**
- Tokens reales (incluso anonimizados — usa UUIDs ficticios).
- Tu propio email / RFC / CURP.
- Holdings reales con montos personales.

Si vas a usar respuestas reales para fixtures, **anonimiza primero**:
- Reemplaza UUIDs con `00000000-0000-4000-8000-...`
- Reemplaza IDs de orden con valores como `100000001`.
- Cambia tu contrato (e.g. `EP47NC` → `AB12CD`).
- Aproxima montos (no uses los exactos).

Los archivos en `experiments/` y `discovery/` están en `.gitignore` — úsalos
para work-in-progress que tenga datos reales.

## Estructura de PRs

PRs ideales son pequeños y enfocados. Para un endpoint nuevo: un solo PR con
modelo + api module + client wiring + tests + docs. Para cambios grandes, abre
issue primero.

Commit message style: imperative, en inglés.
```
Add cash_transactions endpoint

- Domain model CashTransaction (Pydantic v2)
- api.cash_transactions.CashTransactions with .list()
- Wire up in GbmClient
- Tests with respx (happy path + pagination)
- docs/02 updated with endpoint shape
```

## Versionado

[SemVer](https://semver.org/):
- v0.x.y son alphas — la API pública puede cambiar entre minors.
- v1.0.0 marcará primera versión estable.

Bump en `src/gbm_mx_api/_version.py` y en `pyproject.toml` simultáneamente.
