# Capital Insight core API

The FastAPI backend connects one Capital Insight user to the four mock banks, the loan service, the mortgage service, and optional Plaid Sandbox accounts. The Next.js app should call this API at `http://localhost:8000`, rather than calling institutions directly.

This is a local demonstration application. Mock services use fictional data and simulated lending decisions. Plaid Sandbox also uses test data. The backend does not send payments, fund loans, implement AI advice, or turn an approved application into a live debt balance.

## 1. Create your private configuration

From the repository root in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup_env.py
```

The script creates `backend/.env` from `.env.example` and generates a random encryption key. It never overwrites an existing `.env` or prints secrets. Run it before the Docker option too; system Python is sufficient for the script.

Keep `.env` private. Commit `.env.example` instead. Keep `ENCRYPTION_KEY` stable: saved institution and Plaid access tokens are encrypted with it. Losing or changing it requires reconnecting those institutions. When no key is configured in development, the application saves a generated key in `backend/data/encryption.key`; preserve it with the database. Configure an explicit key outside development.

Plaid keys are optional. Leave them blank to use all six local mock providers. Unconfigured Plaid endpoints return `503` with a configuration message.

## 2. Start the backend and all six services

The simplest full setup uses Docker Desktop with its engine running. From `backend/`:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f api
```

This starts the core API, PostgreSQL, four banks, mock loans, and mock mortgages. The Compose stack uses persistent volumes and fixed PostgreSQL credentials for this local demo only. PostgreSQL is available inside the Compose network; it has no published host port. The API and mock service ports bind to localhost.

| Component | URL | Demo institution email |
| --- | --- | --- |
| Core API Swagger | http://localhost:8000/docs | Register your own app user |
| Chase | http://localhost:8001/docs | customer1@chase.example.test |
| Amex | http://localhost:8002/docs | customer1@amex.example.test |
| PNC | http://localhost:8003/docs | customer1@pnc.example.test |
| Discover | http://localhost:8004/docs | customer1@discover.example.test |
| Loans | http://localhost:8005/docs | customer1@loans.example.test |
| Mortgages | http://localhost:8006/docs | customer1@mortgages.example.test |

Stop any older service instances occupying ports 8000-8006 before starting this stack. Use this stack or the services' individual Compose projects; starting both will conflict on those ports.

```powershell
# Stop containers while preserving demo records and connections.
docker compose down
```

### Run Python locally instead

From `backend/`, after creating the environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If port 8000 is already occupied, use `--port 8007` and change `$api` and the frontend `BACKEND_API_URL` to `http://localhost:8007`.

Local development defaults to SQLite at `backend/data/capital_insight.db`. The full Compose setup overrides `DATABASE_URL` to use PostgreSQL with the same application models. To use a separate PostgreSQL database locally, set a `postgresql+psycopg://...` URL in `.env`.

Start mock services separately using their READMEs, or run only the six mock containers from this Compose file:

```powershell
docker compose up --build -d chase amex pnc discover loans mortgages
```

The default local `MOCK_SERVICE_URLS` points to ports 8001-8006. You can start just the providers you need. Unavailable linked providers are reported as errors in aggregation responses. No failed request is silently replaced by fixtures.

## 3. Register and authorize your Capital Insight user

In another PowerShell terminal:

```powershell
$api = "http://localhost:8000"
$credentials = @{
    email = "demo@example.test"
    password = "ExampleDemoPassword2026!"
} | ConvertTo-Json

$session = Invoke-RestMethod -Method Post -Uri "$api/v1/auth/register" `
    -ContentType "application/json" -Body $credentials
$headers = @{ Authorization = "Bearer $($session.access_token)" }

Invoke-RestMethod -Uri "$api/v1/auth/me" -Headers $headers
Invoke-RestMethod -Uri "$api/v1/providers" -Headers $headers
```

Registration creates an app user and returns a session token. Passwords require at least ten characters and are hashed; app session tokens are stored as hashes. If the email is already registered, use `POST /v1/auth/login` with the same JSON instead. `POST /v1/auth/logout` revokes the current session. By default sessions expire after 24 hours.

The app token authenticates requests to the core API. It is separate from each institution's short-lived token, which stays encrypted in the backend database. The backend checks ownership when reading connections and records.

In Swagger, register or log in, then click **Authorize** and paste the app `access_token`. Do not paste a mock-service token there.

## 4. Connect a mock institution

Request a code for Chase using your app authorization:

```powershell
$provider = "chase"
$email = "customer1@chase.example.test"
$body = @{ email = $email } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/v1/connections/$provider/request-code" `
    -Headers $headers -ContentType "application/json" -Body $body
```

In a terminal in `backend/`, read the selected service's log:

```powershell
docker compose logs --tail 30 chase
```

Find the six-digit **DEVELOPMENT ONLY** code. The API does not send an email or return this code. If running the service without Docker, read its Python terminal instead. Compose enables `DEMO_MODE=true` for the six mock services.

```powershell
$code = Read-Host "Enter the six-digit code from the Chase log"
$body = @{ email = $email; code = $code } | ConvertTo-Json
$connection = Invoke-RestMethod -Method Post `
    -Uri "$api/v1/connections/$provider/verify-code" `
    -Headers $headers -ContentType "application/json" -Body $body

Invoke-RestMethod -Uri "$api/v1/connections" -Headers $headers
$accounts = Invoke-RestMethod -Uri "$api/v1/accounts" -Headers $headers
$accounts | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri "$api/v1/dashboard" -Headers $headers
```

Repeat with provider `amex`, `pnc`, `discover`, `loans`, or `mortgages` and its matching demo email. Read `docker compose logs --tail 30 loans` for the loan service, for example. The same app user may explicitly connect different synthetic service customers; matching emails or customer numbers never auto-link identities.

Codes expire after five minutes, are single use, and allow five attempts. Requests have a 30-second cooldown. Mock access tokens expire after 30 minutes; reconnect when the core API reports `409` for an expired institution connection. A new registration has no linked providers, so empty aggregates are expected until you verify a connection.

Use `DELETE /v1/connections/{connection_id}` to disconnect a provider and remove its cached transactions. For Plaid, disconnecting also removes the upstream Item.

## 5. Accounts, lending, and repayment previews

`GET /v1/accounts`, `GET /v1/loans`, and `GET /v1/mortgages` return `{ "items": [...], "errors": [...], "complete": true }`. Each item keeps its source and connection identifiers. Check `errors` and `complete` before presenting a combined total as complete. Provider outages return available data with explicit errors.

For mock bank transactions, use an account's normalized ID as returned by `/v1/accounts`. The ID combines the connection and remote account ID as `connection_id:remote_id`:

```powershell
$accountId = $accounts.items[0].id
Invoke-RestMethod -Uri "$api/v1/accounts/$accountId/transactions?limit=10&offset=0" `
    -Headers $headers
```

Supported filters include `start_date`, `end_date`, and `category`. Bank transaction pages preserve `{ items, total, limit, offset }`; limits are 1-100. Plaid transaction reads use the dedicated endpoints below.

For a verified loan or mortgage connection, copy its ID from `/v1/connections`:

```powershell
$connectionId = Read-Host "Loan or mortgage connection ID"
Invoke-RestMethod -Uri "$api/v1/connections/$connectionId/offers" -Headers $headers
Invoke-RestMethod -Uri "$api/v1/connections/$connectionId/applications" -Headers $headers

# Example for a loans connection; use a term allowed by its offer.
$application = @{
    loan_type = "personal_loan"
    amount = "10000.00"
    term_months = 36
    annual_income = "72000.00"
    existing_monthly_debt = "300.00"
    credit_score = 720
} | ConvertTo-Json

$decision = Invoke-RestMethod -Method Post `
    -Uri "$api/v1/connections/$connectionId/applications" `
    -Headers $headers -ContentType "application/json" -Body $application
$decision | ConvertTo-Json -Depth 8
```

For a mortgage connection the application body is different:

```json
{
  "property_value": "350000.00",
  "down_payment": "70000.00",
  "term_months": 360,
  "annual_income": "120000.00",
  "existing_monthly_debt": "500.00",
  "credit_score": 740
}
```

Use `GET /v1/connections/{connection_id}/records/{record_id}/schedule` for an approved loan or mortgage record. A submitted application may return `201` with `status: "declined"`; inspect its decision. Declined records have no schedule (`409`). Mortgage previews show principal and interest only, excluding taxes, insurance, PMI, escrow, and closing costs.

Loan and mortgage application amounts are original financed amounts, not live outstanding balances. Their schedules are forecasts, not paid installments. The dashboard therefore totals supported account balance snapshots and reports its coverage; it excludes these forecast-only records and unsupported types. A bank-reported loan balance can be included because it is an account snapshot. Checking, savings, CDs, and IRAs are assets; credit-card and bank loan balances are liabilities. Totals stay separate by currency. Do not label the partial result as a complete household net worth. The same real account linked through both a bank and Plaid requires user reconciliation to prevent double counting. Mock records use the fixed seed date `2026-11-01`; values do not become live simply because you fetched them today.

All money at the API boundary is a decimal string. Rates are fractions (`"0.0625"` means 6.25%). Use decimal-safe arithmetic or integer cents in the frontend.

## 6. Add Plaid Sandbox

Get a client ID and Sandbox secret from the [Plaid Dashboard](https://dashboard.plaid.com/) and put them in **backend/.env**:

```dotenv
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET=your_sandbox_secret
PLAID_ENVIRONMENT=sandbox
PLAID_PRODUCTS=["transactions"]
PLAID_COUNTRY_CODES=["US"]
```

Use your Sandbox secret for this environment. Sandbox uses test data; it does not require your real bank credentials. See the [official Plaid Quickstart](https://plaid.com/docs/quickstart/). Restart the local server after changing `.env`; with Docker, recreate the API container so it receives the new environment:

```powershell
docker compose up -d --force-recreate api
```

The following backend-only demo bypasses Link in Sandbox. It creates a public token, exchanges it, fetches accounts, and imports transactions:

```powershell
$public = Invoke-RestMethod -Method Post -Uri "$api/v1/plaid/sandbox/public-token" `
    -Headers $headers -ContentType "application/json" `
    -Body (@{ institution_id = "ins_109508" } | ConvertTo-Json)

$plaid = Invoke-RestMethod -Method Post -Uri "$api/v1/plaid/exchange-public-token" `
    -Headers $headers -ContentType "application/json" `
    -Body (@{ public_token = $public.public_token } | ConvertTo-Json)

$plaidConnectionId = $plaid.id
Invoke-RestMethod -Uri "$api/v1/plaid/connections/$plaidConnectionId/accounts" -Headers $headers
Invoke-RestMethod -Method Post -Uri "$api/v1/plaid/connections/$plaidConnectionId/sync" -Headers $headers
Invoke-RestMethod -Uri "$api/v1/plaid/connections/$plaidConnectionId/transactions?limit=25&offset=0" `
    -Headers $headers
```

The backend encrypts the exchanged Plaid access token and never returns it to the frontend. The public-token shortcut is Sandbox-only; Plaid documents this testing flow in its [Sandbox API reference](https://plaid.com/docs/api/sandbox/).

The sync endpoint persists transactions and its cursor. Subsequent syncs apply additions, modifications, and removals. Initial data may take time to become available; an empty first sync can be valid. Retry sync later. Transaction reads use locally imported records and support `account_id`, `limit`, and `offset`. This implementation uses explicit sync requests; it does not install a webhook endpoint or background scheduler. See Plaid's [Transactions API reference](https://plaid.com/docs/api/products/transactions/).

### Future Next.js Link UI

The backend endpoints are ready; no Plaid frontend component is added by this backend task:

1. The signed-in frontend calls `POST /v1/plaid/link-token` with its app session token.
2. Pass the returned `link_token` to Plaid Link, for example through `react-plaid-link`.
3. Link's success callback supplies `public_token`; send it to `POST /v1/plaid/exchange-public-token`.
4. Refresh `/v1/connections` and `/v1/accounts`, then request a Plaid sync for transactions.

Keep `PLAID_SECRET`, `ENCRYPTION_KEY`, institution tokens, and Plaid access tokens on the server. Do not place them in `NEXT_PUBLIC_` variables or browser storage. When OAuth requires a redirect, register the exact URI in the Plaid Dashboard and set `PLAID_REDIRECT_URI` to match. The Sandbox shortcut above works before this UI exists.

For an existing Plaid Item that needs reauthorization, request `POST /v1/plaid/link-token` with `{ "connection_id": "your-owned-connection-id" }` and use the token to open Link in update mode.

## Configuration reference

| Variable | Default / purpose |
| --- | --- |
| `ENVIRONMENT` | `development`; enables local encryption-key generation when unset |
| `DATABASE_URL` | Local SQLite; Compose overrides with PostgreSQL |
| `ENCRYPTION_KEY` | Fernet key for stored upstream tokens; generated by setup script |
| `SESSION_TTL_SECONDS` | `86400` |
| `REQUEST_TIMEOUT_SECONDS` | `15` |
| `CORS_ORIGINS` | JSON array, default `["http://localhost:3000"]` |
| `MOCK_SERVICE_URLS` | JSON map of provider IDs to fixed backend-only upstream URLs |
| `PLAID_CLIENT_ID`, `PLAID_SECRET` | Optional credentials from your Plaid Dashboard |
| `PLAID_ENVIRONMENT` | `sandbox` by default |
| `PLAID_PRODUCTS` | JSON array, default `["transactions"]` |
| `PLAID_COUNTRY_CODES` | JSON array, default `["US"]` |
| `PLAID_REDIRECT_URI` | Optional configured Link OAuth redirect |

JSON arrays and maps must remain valid JSON in `.env`. The core service does not need the mock services' signing secrets; each provider issues and verifies its own scoped tokens. Upstream URLs are configured by the operator, never supplied by browser requests.

## Endpoint reference and checks

Interactive schemas and request examples: http://localhost:8000/docs. Machine-readable contract: http://localhost:8000/openapi.json. Public health check: `GET /health`.

| Routes | Purpose |
| --- | --- |
| `POST /v1/auth/register`, `POST /v1/auth/login` | Create an app session |
| `GET /v1/auth/me`, `POST /v1/auth/logout` | Inspect/revoke current session |
| `GET /v1/providers`, `GET /v1/connections` | Discover providers and your linked connections |
| `DELETE /v1/connections/{id}` | Disconnect and remove cached transactions |
| `POST /v1/connections/{provider}/request-code`, `/verify-code` | Consent to a mock provider |
| `GET /v1/accounts` | Linked bank and Plaid accounts |
| `GET /v1/accounts/{account_id}/transactions` | Mock bank account transactions |
| `GET /v1/loans`, `GET /v1/mortgages` | Normalized linked lending records |
| `GET /v1/connections/{id}/offers` | Loan/mortgage offers |
| `GET` / `POST /v1/connections/{id}/applications` | List/submit simulated applications |
| `GET /v1/connections/{id}/records/{record_id}/schedule` | Projected repayment schedule |
| `GET /v1/dashboard` | Explicitly scoped balance summary |
| `POST /v1/plaid/link-token` | Initialize frontend Plaid Link |
| `POST /v1/plaid/sandbox/public-token` | Backend-only Sandbox test helper |
| `POST /v1/plaid/exchange-public-token` | Save an owned Plaid connection |
| `GET /v1/plaid/connections/{id}/accounts` | Plaid account snapshots |
| `POST /v1/plaid/connections/{id}/sync` | Import transaction updates |
| `GET /v1/plaid/connections/{id}/transactions` | Read imported transactions |

Run focused backend tests from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests exercise mocked provider responses; they do not establish live Plaid connectivity. A successful real Sandbox walkthrough requires your own keys and network access. Docker configuration validation does not prove that the engine is running or containers built successfully.

Common responses: `401` means log in again, `404` means unavailable/not owned, `409` includes duplicate users, expired institution connections, or unavailable declined schedules, `422` means request validation failed, `429` means mock consent cooldown, and `503` on Plaid means missing configuration. Aggregate errors identify individual unavailable providers rather than hiding partial coverage.
