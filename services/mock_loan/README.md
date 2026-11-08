# Mock loan platform

A loan-only Python API with fictional customers, loan offers, simulated application decisions, and cent-accurate repayment previews. It is an independent service with its own Python modules, configuration, database, tests, and container. It does not import or require mock_bank.

## Run (PowerShell)

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r services/mock_loan/requirements.txt
Set-Location services/mock_loan
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8005
```

Open http://localhost:8005/docs. Startup creates `data/loans.db` with five synthetic customers and ten approved simulated loan records (one personal and one auto loan each). Data persists on restart. No deposit or credit-card endpoints are exposed by this app. Configuration is read from this service's `.env`; environment variables override it. Use LENDER_ID and LENDER_NAME for the lender identity. Do not point this app at an existing bank database.

## Authenticate and apply

Run in another PowerShell terminal:

```powershell
$base = "http://localhost:8005"
$email = "customer1@loans.example.test"
Invoke-RestMethod -Method Post -Uri "$base/v1/auth/request-code" -ContentType "application/json" -Body (@{email=$email} | ConvertTo-Json)
$code = Read-Host "Enter DEVELOPMENT ONLY code from the server terminal"
$auth = Invoke-RestMethod -Method Post -Uri "$base/v1/auth/verify-code" -ContentType "application/json" -Body (@{email=$email; code=$code} | ConvertTo-Json)
$headers = @{Authorization="Bearer $($auth.access_token)"}
Invoke-RestMethod "$base/v1/loan-offers"
$body = @{loan_type="personal_loan"; amount="10000.00"; term_months=36; annual_income="72000.00"; existing_monthly_debt="300.00"; credit_score=720} | ConvertTo-Json
$application = Invoke-RestMethod -Method Post -Uri "$base/v1/loan-applications" -ContentType "application/json" -Headers $headers -Body $body
$application
Invoke-RestMethod "$base/v1/loans" -Headers $headers
Invoke-RestMethod "$base/v1/loans/$($application.id)/schedule" -Headers $headers
```

The mock code expires in five minutes, allows five attempts, is single use, and has a 30-second request cooldown. Tokens expire in 30 minutes. In Swagger, paste `access_token` into Authorize. Customers 1 through 5 use `customerN@loans.example.test`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Public health check |
| GET | /v1/lender | Public lender metadata |
| GET | /v1/loan-offers | Public personal, auto, and mortgage offers |
| POST | /v1/auth/request-code | Request mock login code |
| POST | /v1/auth/verify-code | Receive signed token |
| GET | /v1/customers/me | Current fictional customer |
| POST | /v1/loan-applications | Apply and receive simulated decision |
| GET | /v1/loan-applications | Your applications, approved and declined |
| GET | /v1/loan-applications/{id} | Your application and decision |
| GET | /v1/loans | Your approved simulated loans |
| GET | /v1/loans/{id} | One of your approved simulated loans |
| GET | /v1/loans/{id}/schedule | Hypothetical repayment schedule |

All customer-specific endpoints require a bearer token. Other customers' records return 404. Invalid inputs return 422. A declined application's schedule returns 409. Submitting an application creates a new record each time.

## Simulation rules

Offers list supported amount ranges, terms, and APR fractions. Personal loans use 9.90%, auto loans 6.50%, mortgages 6.25%. A fictional application is approved when its self-reported score is at least 620 and existing monthly debt plus the proposed payment is no more than 40% of monthly income. Otherwise it is declined with an explanation. These fixed rules are for software demonstrations only; there is no real underwriting, credit inquiry, disbursement, or payment processing.

Monthly payments use the standard fixed-rate amortization formula, with Decimal arithmetic and cents rounding. Schedules begin one month after creation, handle month-end dates, and adjust the final installment to clear rounding residue. The entire schedule is a projection: there is no recorded payment history or live outstanding balance. Amounts and rates are returned as decimal strings; USD is the only currency.

The future main backend can call these endpoints with HTTPX and a server-held token. No frontend is included.

## Tests

From the repository root:

```powershell
python -m pytest services/mock_loan/tests -q
```

## Seed and Docker

From `services/mock_loan`, run `python -m app.seed` to generate data explicitly. Startup also seeds automatically. Repeated runs preserve existing data. Faker uses DATA_SEED; dates use SEED_DATE. Secrets and verification codes remain securely random.

```powershell
docker compose up --build -d
docker compose logs -f mock-loan
```

The container listens on 8000 and host port 8005. A dedicated named volume persists loan data. This service can run alongside mock_bank on ports 8001-8004. Demo codes are logged only with DEMO_MODE=true, which Compose enables for local use.

Configuration: LENDER_ID=loans, LENDER_NAME=Capital Insight Mock Loans, DATABASE_URL=sqlite:///./data/loans.db, DATA_SEED=505, SEED_DATE=2026-11-01. Authentication settings: DEMO_MODE (false by default), CODE_TTL_SECONDS=300, CODE_ATTEMPT_LIMIT=5, REQUEST_COOLDOWN_SECONDS=30, TOKEN_TTL_SECONDS=1800. An optional SIGNING_SECRET must have at least 32 characters; otherwise a per-lender random secret persists in SQLite. Never share database files between lenders. No SSNs or actual customer records are used.

Run both service test suites from the repository root with `python -m pytest services/mock_bank/tests services/mock_loan/tests -q`. From this service directory, use `python -m pytest tests -q`.


## Optional real email codes

See [EMAIL_SETUP.md](../../EMAIL_SETUP.md) for free Gmail SMTP setup. Configure the repository-root private `.env.mail`, then restart this service. SMTP mode sends fictional customers' codes to the configured real demo inbox and suppresses code logging. Default log-only behavior remains available.
