# Capital Insight mock banking API

A standalone, read-only FastAPI microservice for entirely fictional financial records. The same Python code runs Chase, American Express, PNC, Discover, or a custom bank. This is a mock consent flow, not a real financial institution login. No email is sent and no payments or balance mutations are exposed.

## Architecture

`main.py` builds an application with its own settings, engine, session factory, and lifespan. `config.py` reads environment variables and `.env`. `models.py` defines SQLAlchemy 2 ORM tables; `schemas.py` defines Pydantic response contracts. Routers handle institution, customer, account, transaction, and authorization requests. `dependencies.py` checks bearer tokens and account ownership. `seed.py` generates a ledger once at startup or through its CLI. Synchronous sessions keep the implementation small.

SQLite supplies portable, persistent, independent bank files without a database server. Foreign keys are enabled on every connection. It suits this low-volume demo; the future main application can still use PostgreSQL independently. Startup creates missing tables, but is not a migration framework. Do not share a file between banks. A persisted bank identifier prevents accidental cross-bank reuse. Back up a database before changing its schema.

## Local setup (PowerShell, Python 3.11+)

Run from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services/mock_bank/requirements.txt
Set-Location services/mock_bank
Copy-Item .env.example .env
python -m app.seed
python -m uvicorn app.main:app --reload --port 8001
```

If an existing virtual environment is available, activate it instead of recreating it. All following local commands assume the `services/mock_bank` working directory. Database paths and `.env` are relative to that directory. Startup seeds automatically too; repeated seeding leaves existing data unchanged.

`.env.example` documents all settings. `DEMO_MODE` defaults to false in code, and the example enables it for local use. The default demo email is `customer1@chase.example.test`; customers 1 through 5 exist in every bank using `customerN@BANK_ID.example.test`. All names are fictional Faker output, addresses use reserved test domains, and identity IDs start with `SYNTH-`. No SSNs are generated or stored.

Configuration:

| Setting | Default | Meaning |
| --- | --- | --- |
| BANK_ID | chase | Bank identifier and token audience |
| BANK_NAME | Chase Mock Bank | Display name |
| DATABASE_URL | sqlite:///./data/chase.db | Dedicated SQLite file |
| DATA_SEED | 101 | Faker and financial PRNG seed |
| SEED_DATE | 2026-11-01 | Fixed ending date of the financial snapshot |
| DEMO_MODE | false | Log development-only consent codes |
| SIGNING_SECRET | random, persisted in SQLite | Optional secret, at least 32 characters |
| CODE_TTL_SECONDS | 300 | Code lifetime |
| CODE_ATTEMPT_LIMIT | 5 | Maximum attempts per issued code |
| REQUEST_COOLDOWN_SECONDS | 30 | Minimum interval per email |
| TOKEN_TTL_SECONDS | 1800 | Signed bearer token lifetime |

A random secret is generated once per bank database, so tokens survive ordinary restarts. Changing an explicit secret invalidates old tokens. Keep the database and secret private. Tokens use HMAC-SHA256 signed JSON with bank audience and expiry; they are deliberately small mock tokens, not JWTs. Verification state is persisted, and SQLite write transactions serialize code issuance/redemption across workers. Codes are securely random and stored as keyed hashes; old codes are invalidated by a new request. Rate limiting is per normalized email, including unknown emails. For an internet-facing system, add global/IP throttling, real delivery, TLS, and a proper identity provider. Demo logs intentionally contain sensitive mock codes: enable only in local demonstrations.

## Start four banks with Docker

From `services/mock_bank`:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f chase
```

| Instance | Host port | Data seed | Persistent volume |
| --- | --- | --- | --- |
| Chase | 8001 | 101 | chase_data |
| Amex | 8002 | 202 | amex_data |
| PNC | 8003 | 303 | pnc_data |
| Discover | 8004 | 404 | discover_data |

Each container listens on 8000 and runs as an unprivileged user. Named volumes preserve each bank database and signing secret across restarts. Compose enables development logging for this local demo. `docker compose down` retains volumes; `down -v` deletes all synthetic data. `.env` is excluded from Docker images.

To run Amex locally in a separate terminal:

```powershell
$env:BANK_ID = "amex"
$env:BANK_NAME = "American Express Mock Bank"
$env:DATABASE_URL = "sqlite:///./data/amex.db"
$env:DATA_SEED = "202"
$env:DEMO_MODE = "true"
python -m uvicorn app.main:app --port 8002
```

Environment variables override `.env`. Add a custom bank by assigning a new ID, display name, file, seed, and port. Unknown IDs receive checking and savings; add a product list in `seed.PRODUCTS` for other combinations. Product choices are seed configuration, not bank-specific route logic. New seed settings do not rewrite existing databases; use a new file to generate a new snapshot.

## End-to-end demo and Swagger

1. Start Chase with the local command above.
2. Open http://localhost:8001/docs. ReDoc is at `/redoc`; the OpenAPI contract is at `/openapi.json`.
3. Request a code for a seeded email.
4. Read the **DEVELOPMENT ONLY** code in the Uvicorn terminal (or `docker compose logs chase`).
5. Verify it to obtain an access token.
6. In Swagger, click **Authorize**, paste only `access_token`, and authorize. Protected routes now send the HTTP Bearer header.
7. List accounts, select one, then read its balance and transactions.

PowerShell walkthrough in a second terminal:

```powershell
$base = "http://localhost:8001"
$email = "customer1@chase.example.test"
Invoke-RestMethod -Method Post -Uri "$base/v1/auth/request-code" -ContentType "application/json" -Body (@{email=$email} | ConvertTo-Json)
$code = Read-Host "Enter development code from bank server logs"
$auth = Invoke-RestMethod -Method Post -Uri "$base/v1/auth/verify-code" -ContentType "application/json" -Body (@{email=$email; code=$code} | ConvertTo-Json)
$headers = @{Authorization="Bearer $($auth.access_token)"}
Invoke-RestMethod "$base/v1/customers/me" -Headers $headers
$accounts = Invoke-RestMethod "$base/v1/accounts" -Headers $headers
$accounts | Format-Table id, account_type, balance
$id = $accounts[0].id
Invoke-RestMethod "$base/v1/accounts/$id/balance" -Headers $headers
Invoke-RestMethod "$base/v1/accounts/$id/transactions?limit=10&offset=0&start_date=2026-08-01&end_date=2026-11-01" -Headers $headers
```

The code expires after five minutes and is single use. Wait 30 seconds before requesting another. Codes never appear in ordinary API responses. Request-code returns the same generic message for known and unknown emails. Failed verification returns 401. A missing, tampered, expired, or wrong-bank token returns 401. Another customer's account is indistinguishable from an absent account: both return 404.

## Endpoint contract

| Method | Path | Access |
| --- | --- | --- |
| GET | /health | Public database liveness |
| GET | /v1/institution | Public metadata |
| POST | /v1/auth/request-code | Public mock code request, 202; cooldown 429 |
| POST | /v1/auth/verify-code | Public code exchange; invalid code 401 |
| GET | /v1/customers/me | Bearer |
| GET | /v1/accounts | Bearer; optional account_type |
| GET | /v1/accounts/{account_id} | Owner only |
| GET | /v1/accounts/{account_id}/balance | Owner only |
| GET | /v1/accounts/{account_id}/transactions | Owner only |

Transactions return `{items, total, limit, offset}`. Limit is 1?100 (default 50), offset is nonnegative, date bounds are inclusive, and category is a validated enum. Results sort by date descending, then stable ID descending. Invalid types, ranges, categories, and reversed date bounds return 422. Errors use FastAPI's `detail` envelope (validation errors contain a list of field issues). Account types and categories are enumerated in Swagger. All financial values are decimal strings, including rates expressed as fractions (0.1800 means 18%). Example balance response:

```json
{"id":"chase-customer-001-checking","currency":"USD","balance":"8000.00","updated_at":"2026-11-01T00:00:00Z"}
```

Example transaction response item (illustrative):

```json
{"id":"demo-tx","account_id":"demo-account","transaction_date":"2026-11-01","description":"Synthetic groceries: Demo Market","merchant":"Demo Market","category":"groceries","amount":"35.00","direction":"debit","transaction_type":"purchase","created_at":"2026-11-01T12:00:00Z"}
```

## Financial data and simplifications

Faker and a local PRNG are seeded independently; stable IDs, dates, names, amounts and product values reproduce for a given configuration and dependency version. Pin dependencies in your deployment if exact cross-version Faker output matters. Random authentication secrets/codes are intentionally not deterministic. Each bank has five customers and at least two accounts per customer. PNC demonstrates every supported type; the other banks use their listed primary products.

Each account exposes `opening_balance`. Checking, savings, and credit cards have activity spanning 90 days through SEED_DATE, including recurring salary/savings contributions or card payments and categorized spending. Ending balance is opening balance plus the complete stored ledger:

- Checking, savings, CD, IRA: credit increases assets, debit decreases assets.
- Credit cards and loans: debit increases amount owed, credit decreases amount owed. A credit-card payment is a credit.

Amounts are nonnegative `Decimal` values; SQLAlchemy uses `Numeric`, and amounts are quantized to cents before calculation. Card payments never exceed the balance; generated balances stay below the credit limit. Card limits/APRs and deposit APYs vary. Balances are snapshots as of SEED_DATE, not live valuations. Dates/timestamps are stored as UTC and restored with timezone information on SQLite reads.

Loans use principal-only monthly repayments, without amortization schedules, interest accrual, escrow, fees, or actual payment execution. `outstanding_principal` equals the derived balance. CDs are static deposits with a maturity date and quoted APY, without interest accrual. IRAs are static aggregate values with a Roth subtype; there are no securities, market prices, tax calculations, investment performance, or contribution-limit checks. `account_value` equals balance. Card APR and minimum payments are illustrative; the service does not model interest cycles. Salary and spending are plausible demo patterns, not a complete household budget. No paired cross-account transfers or real account numbers are modeled.

## Tests

From the repository root with the environment activated:

```powershell
python -m pytest services/mock_bank/tests -q
```

Or from this service directory: `python -m pytest tests -q`. Tests use temporary isolated SQLite files and TestClient; no cloud credentials, external APIs, or email services are needed. They cover health, OpenAPI, auth success/failure/expiry/replay/cooldown/attempt limits, ownership, balances, filtering, pagination, decimal serialization, reproducibility, idempotency, restart persistence, foreign keys, ledger consistency, all bank profiles, and database isolation.

## Future main-backend integration

The main FastAPI backend can keep a registry of bank base URLs, request mock consent for the fictional email, exchange the entered code, and call `/v1/customers/me`, `/v1/accounts`, and paginated transaction endpoints using HTTPX. Store tokens server-side, handle expiry by repeating consent, and key imported account/transaction IDs by institution. Parse decimal strings as Python `Decimal`; retain direction and account type to distinguish debt from assets. Use `total` and offsets to fetch all history. Configure HTTPX timeouts and handle 401/404/422/429 explicitly. This service does not implement the frontend, PostgreSQL aggregator, AI, or NVIDIA integration.
