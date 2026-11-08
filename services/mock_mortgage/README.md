# Capital Insight Mock Mortgage API

An independent mortgage-only FastAPI service under `services/mock_mortgage`. It has its own configuration, Python modules, SQLite database, tests, Docker image, and persistent volume. It does not import mock_bank or mock_loan.

The API provides fictional borrowers, fixed-rate mortgage offers, applications with simulated decisions, and principal-and-interest repayment schedules. No real credit checks, underwriting, disbursements, or payments occur.

## Run locally (PowerShell)

From the repository root with Python 3.11+:

```powershell
# If needed, create the environment first: py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services/mock_mortgage/requirements.txt
Set-Location services/mock_mortgage
Copy-Item .env.example .env
python -m app.seed
python -m uvicorn app.main:app --reload --port 8006
```

Open http://localhost:8006/docs. ReDoc is at `/redoc` and OpenAPI is at `/openapi.json`. Seeding also runs automatically at startup and preserves existing data. The default SQLite file is `services/mock_mortgage/data/mortgages.db`. Five fictional borrowers each receive one approved mortgage with varied property values and 15-, 20-, or 30-year terms. No real identities or SSNs are used.

Configuration is read from this service's `.env`. Shell environment variables take precedence; clear previous DATABASE_URL/LENDER_ID overrides when switching services.

| Setting | Default |
| --- | --- |
| LENDER_ID | mortgages |
| LENDER_NAME | Capital Insight Mock Mortgages |
| DATABASE_URL | sqlite:///./data/mortgages.db |
| DATA_SEED | 606 |
| SEED_DATE | 2026-11-01 |
| DEMO_MODE | false; example enables it |
| CODE_TTL_SECONDS | 300 |
| CODE_ATTEMPT_LIMIT | 5 |
| REQUEST_COOLDOWN_SECONDS | 30 |
| TOKEN_TTL_SECONDS | 1800 |
| SIGNING_SECRET | Random per-lender secret persisted in SQLite; optional override of at least 32 characters |

Each lender must use a separate SQLite file. The seed checks the platform and lender identifiers before reusing a database. DATA_SEED controls Faker output; SEED_DATE fixes snapshot timestamps. Authentication secrets/codes intentionally remain random. Existing seed data is never overwritten. Use a new database file to generate a fresh snapshot. Foreign keys are enabled and timestamps are UTC.

## Authenticate and submit a mortgage application

In a second PowerShell terminal:

```powershell
$base = "http://localhost:8006"
$email = "customer1@mortgages.example.test"
Invoke-RestMethod -Method Post -Uri "$base/v1/auth/request-code" -ContentType "application/json" -Body (@{email=$email} | ConvertTo-Json)
$code = Read-Host "Enter DEVELOPMENT ONLY code from the mortgage server terminal"
$auth = Invoke-RestMethod -Method Post -Uri "$base/v1/auth/verify-code" -ContentType "application/json" -Body (@{email=$email; code=$code} | ConvertTo-Json)
$headers = @{Authorization="Bearer $($auth.access_token)"}
Invoke-RestMethod "$base/v1/mortgage-offers"
$body = @{
    property_value="350000.00"
    down_payment="70000.00"
    term_months=360
    annual_income="120000.00"
    existing_monthly_debt="500.00"
    credit_score=740
} | ConvertTo-Json
$application = Invoke-RestMethod -Method Post -Uri "$base/v1/mortgage-applications" -ContentType "application/json" -Headers $headers -Body $body
$application
Invoke-RestMethod "$base/v1/mortgages" -Headers $headers
Invoke-RestMethod "$base/v1/mortgages/$($application.id)/schedule" -Headers $headers
```

Customers 1 through 5 use `customerN@mortgages.example.test`. With default log delivery, codes appear in server logs with DEMO_MODE=true, never in API responses; email is sent only when SMTP delivery is configured. Codes expire in five minutes, are single use, allow five attempts, and have a 30-second request cooldown. Successful verification returns a signed, lender-scoped token valid for 30 minutes. In Swagger, paste only `access_token` into Authorize. Missing/invalid/expired tokens return 401. Other borrowers' records return 404. A declined application's schedule returns 409. Validation errors return 422. Each POST creates a separate application.

## API endpoints

| Method | Path | Access / purpose |
| --- | --- | --- |
| GET | /health | Public database health |
| GET | /v1/lender | Public fictional lender metadata |
| GET | /v1/mortgage-offers | Public fixed-rate mortgage offer |
| POST | /v1/auth/request-code | Public mock verification request |
| POST | /v1/auth/verify-code | Public token exchange |
| GET | /v1/customers/me | Authenticated fictional borrower |
| POST | /v1/mortgage-applications | Submit and receive simulated decision |
| GET | /v1/mortgage-applications | Your approved and declined applications |
| GET | /v1/mortgage-applications/{id} | Your application decision |
| GET | /v1/mortgages | Your approved simulated mortgages |
| GET | /v1/mortgages/{id} | Your approved mortgage details |
| GET | /v1/mortgages/{id}/schedule | Hypothetical repayment schedule |

## Mortgage simulation

Financed amount = property_value - down_payment. `loan_to_value` = financed amount / property_value, rounded to four decimal places. A $350,000 property and $70,000 down payment produces a $280,000 mortgage and 0.8000 LTV.

The fictional fixed APR is 0.0625 (6.25%). Advertised financed amounts range from $50,000 to $750,000; terms are 180, 240, or 360 months. The only accepted mortgage_type is `mortgage` (the default). Down payment must be nonnegative and less than property value. Amounts outside the advertised range or unsupported terms return 422.

Simulation approves applications when the down payment is at least 5%, self-reported credit score is at least 620, and proposed principal-and-interest payment plus existing monthly debt is no more than 40% of monthly gross income. Failed eligibility produces a saved declined application with an explanation. These are fictional software rules, not lending guidance.

Payments use Decimal arithmetic and the fixed-rate amortization formula, rounded to cents. Each schedule splits payment into principal and interest; the final payment clears rounding residue. Dates fall monthly after application creation and handle short months. Responses serialize all money and rates as decimal strings. Example: the $280,000, 30-year mortgage above has a simulated monthly principal-and-interest payment of $1,724.01.

Schedules omit property taxes, insurance, PMI, escrow, points, closing costs, adjustable rates, prepayments, and actual payment history. Approved records are simulations, not funded loans or live balance accounts. The API only supports USD.

## Docker

From `services/mock_mortgage`:

```powershell
docker compose up --build -d
docker compose logs -f mock-mortgage
```

The container listens on port 8000 and exposes host port 8006. The `mortgage_data` volume preserves the database and signing secret across restarts. Compose enables local demo logging. `docker compose down` retains data; adding `-v` deletes it. This can run alongside mock_bank (8001-8004) and mock_loan (8005).

## Tests and main-backend integration

From the repository root:

```powershell
python -m pytest services/mock_mortgage/tests -q
python -m pytest services/mock_bank/tests services/mock_loan/tests services/mock_mortgage/tests -q
```

From this service directory: `python -m pytest tests -q`. Tests use temporary SQLite files and no external services. Coverage includes authentication, expiry, attempts, replay, rate limits, ownership, decisions, property validation, amortization, reproducible seeds, restart persistence, and foreign keys.

The main backend can use HTTPX to exchange mock codes, retain the token server-side, and fetch borrower mortgages and schedules. Parse financial strings as Decimal. Keep institution-scoped IDs when importing records into the main application. This service includes no frontend or AI integration.


## Optional real email codes

See [EMAIL_SETUP.md](../../EMAIL_SETUP.md) for free Gmail SMTP setup. Configure the repository-root private `.env.mail`, then restart this service. SMTP mode sends fictional customers' codes to the configured real demo inbox and suppresses code logging. Default log-only behavior remains available.
