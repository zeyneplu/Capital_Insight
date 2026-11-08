# Capital Insight - contributor and agent guide

This file applies across the repository. Read `frontend/AGENTS.md` too when working on the frontend. This is the handoff for the Next.js frontend and the merged core backend.

## Product and current state

Capital Insight is a HackUTD 2026 financial wellness application. The intended experience combines a customer's bank accounts, transactions, loans, and mortgages into one dashboard, then eventually adds AI financial analysis and planning.

What exists today:

- `backend/`: core API (FastAPI) with sessions, server-side token custody, and aggregation over the mock services (see `backend/Readme.md`). The frontend uses anonymous /api/v1 sessions; /v1 also supplies application login, PostgreSQL-capable storage, and Plaid. AI integration remains future work.
- `frontend/`: the Capital Insight UI (see `frontend/Readme.md`). Fixtures by default; `DATA_SOURCE=http` uses the core API.
- `services/mock_bank/`: working synthetic banking API; one configurable instance per bank.
- `services/mock_loan/`: independent synthetic loan API.
- `services/mock_mortgage/`: independent synthetic mortgage API. Use this spelling.

The intended stack is Next.js for the frontend, Python/FastAPI for the main backend, PostgreSQL for the main application, SQLite inside the mock services, and NVIDIA Nemotron for future analysis. The main backend and the mock services implement API behavior.

## Frontend task boundaries

Build the frontend now using deterministic local fixtures. It must work when no Python services or main backend are running. Connect real services through a replaceable data layer later.

Work in `frontend/`. Preserve the mock services and their API contracts. Do not implement the main backend, PostgreSQL schema, or AI integration as part of routine frontend work. Small Next.js Route Handlers may serve fixture responses or proxy approved upstream calls when needed; they are not the main banking aggregator.

Do not run create-next-app again: the app already exists. Preserve the npm lockfile and the generated instruction block in `frontend/AGENTS.md`.

## Start after pulling (PowerShell)

From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Use a Node version supported by the installed Next.js package. Treat `frontend/package.json` and `package-lock.json` as the source of truth for versions and scripts. At this handoff the package declares Next.js 16.4.5, React 19.3.0, TypeScript, and Tailwind 4.

Do not upgrade dependencies just to start frontend work. If npm ci fails, read its error before changing the lockfile. The generated frontend instructions require reading relevant installed Next.js guides under `frontend/node_modules/next/dist/docs/` before coding. These local docs take precedence over remembered APIs for older releases.

## Suggested first implementation

These routes are proposed UI routes, not existing pages or promised backend endpoints:

| Route | Purpose |
| --- | --- |
| `/` | Dashboard: assets, liabilities, net worth, spending summary, upcoming obligations |
| `/accounts` | Connected institutions and account cards, with account-type filtering |
| `/accounts/[accountId]` | Account details and transaction list, dates, categories, and pagination |
| `/loans` | Approved simulated loans, offers, applications, and repayment previews |
| `/mortgages` | Mortgage details, property/down-payment application, and amortization preview |
| `/connect` | Choose an institution and step through simulated connection/consent |
| `/insights` | Clearly labeled sample financial insights until the AI backend exists |

Start with the shared app shell and dashboard, then accounts/transactions, then loans/mortgages, then the connection flow. Keep the first version focused and usable; do not invent real payments, transfers, or loan funding.

Use reusable cards, tables, form inputs, status badges, and feedback components. Build responsive layouts for phone and desktop, semantic headings, labeled fields, keyboard navigation, visible focus states, and accessible contrast. Include loading, empty, error, and success states. Format USD and dates consistently. Use a visible Demo data indicator for fixtures and simulated actions.

The user has not specified a final design system or visual reference. Establish a consistent visual style without treating an unapproved palette or layout as a product requirement.

## File organization and data boundary

Continue using the existing root-level `frontend/app/`; do not introduce a second `src/app/` or a Pages Router.

Suggested files to create as needed (these do not exist yet):

```text
frontend/
  app/                  # routes, layouts, loading and error views
  components/           # reusable UI and feature components
  lib/
    types.ts            # API response types and normalized view models
    data/               # one async interface used by pages/components
      index.ts          # selects fixture or future HTTP implementation
      fixtures.ts       # deterministic synthetic records
      mock-provider.ts  # fixture-backed implementation
      http-provider.ts  # optional future backend implementation
    format.ts           # currency, percentage and date formatting
```

Keep components unaware of which provider supplies data. For example, design typed async functions such as getDashboard(), listAccounts(), listTransactions(filters), listLoans(), listMortgages(), requestCode(), and verifyCode(). These are proposed frontend functions, not existing API methods. Route components call this layer instead of embedding fetch URLs or fixtures throughout JSX.

Give both providers matching result shapes. Define the view model separately from raw service JSON when aggregation needs additional institution metadata. Keep source service + institution + record ID when normalizing data. An HTTP adapter should translate service responses into the same view models, so switching providers does not require rewriting pages.

Proposed configuration, to implement and document when adding the provider:

```dotenv
# frontend/.env.local - do not commit
DATA_SOURCE=mock
# Set only when the main FastAPI backend exists:
# BACKEND_API_URL=http://localhost:8000
```

These variables are a convention to implement, not existing app behavior. Default to fixtures without requiring an .env.local file. DATA_SOURCE should be selected on the server; do not import server-only configuration into Client Components. Keep BACKEND_API_URL and service tokens server-side. Do not prefix secrets with NEXT_PUBLIC_. Add a sanitized .env.example if useful and explicitly allow it in frontend/.gitignore if that template ignores all .env files.

Use Server Components for layouts and data reads where appropriate; use small Client Components for filters, dialogs, forms, and other interactions. Do not mark the entire app as client-only by default. Follow the installed Next.js docs for dynamic route params, cookies, caching, and other version-sensitive APIs.

## Fixture rules

Fixtures should demonstrate the full UI without networks or credentials:

- Use fictional names, reserved example.test emails, stable IDs, and fixed dates. Never use real financial records or SSNs.
- Include checking, savings, credit-card, loan, and mortgage examples; nullable subtype fields should be handled safely.
- Give account detail views enough transactions to exercise pagination and category/date filtering.
- Calculate summary cards/charts from the same fixture records, rather than hardcoding conflicting totals.
- Keep a fixed snapshot date and label it; existing mock services default to SEED_DATE=2026-11-01. Avoid presenting historical fixture dates as live balances or overdue real obligations.
- Simulated connection/application state can be session-local; clearly describe persistence limits. Demo consent may use a documented fixture-only code, but it must not be confused with live service codes.
- Never silently replace a failed live request with fixtures. Show an error or let the user explicitly switch to demo mode.

Money from APIs is a decimal string, such as "16487.05". Retain that representation at the boundary. Use integer cents or decimal-safe arithmetic for financial calculations; do not sum currency using binary floating-point. Formatting for display can use Intl.NumberFormat. Rates are fractions: "0.0625" means 6.25%.

Balances for checking/savings/IRAs/CDs are assets; credit-card and loan balances represent amounts owed. For assets, credits increase balance and debits decrease it; for debts, debits increase debt and credits decrease it. Net worth is assets minus liabilities.

Avoid double counting: mock_bank already supports loan and mortgage account types, mock_loan also offers mortgages, and mock_mortgage is a separate provider. Choose a coherent fixture portfolio or explicitly map duplicates. Do not assume matching emails or customer numbers across services identify the same person; each service has its own synthetic customers and token scope.

Approved application records expose original financed amount and a projected schedule, not a live outstanding balance or recorded payment history. Do not relabel them as current debt balances or completed payments. A dashboard needs an explicit fixture/view-model snapshot for those values until the backend supplies them.

## Existing service contracts (optional live integration)

Read each service README and `app/schemas.py` before integrating. Running services expose `/docs`, `/redoc`, and `/openapi.json`; their OpenAPI contracts are authoritative. The main backend has no contract yet, so keep any proposed aggregator routes clearly marked as proposals.

| Service | Default local port | Demo email |
| --- | --- | --- |
| Chase mock_bank | 8001 | customer1@chase.example.test |
| Amex mock_bank | 8002 | customer1@amex.example.test |
| PNC mock_bank | 8003 | customer1@pnc.example.test |
| Discover mock_bank | 8004 | customer1@discover.example.test |
| mock_loan | 8005 | customer1@loans.example.test |
| mock_mortgage | 8006 | customer1@mortgages.example.test |

These are configured ports, not a guarantee that services are running after a pull. Docker Compose for mock_bank starts all four banks; loan and mortgage services have independent Compose files.

Shared mock authorization:

1. POST `/v1/auth/request-code` with `{ "email": "customer1@loans.example.test" }` (use the selected service's registered demo email).
2. With DEMO_MODE=true, read the six-digit DEVELOPMENT ONLY code from that service's server logs. With AUTH_CODE_DELIVERY=smtp and root .env.mail configured, codes go to a fixed real demo inbox; otherwise DEMO_MODE logs them. Ordinary responses never contain the code. See EMAIL_SETUP.md.
3. POST `/v1/auth/verify-code` with `{ "email": "...", "code": "123456" }`, using the actual generated code.
4. Receive `{ "access_token": "...", "token_type": "bearer", "expires_in": 1800 }`.
5. Send `Authorization: Bearer <access_token>` for protected calls. GET `/v1/customers/me` returns the authenticated fictional customer.

Defaults: code lifetime five minutes, five attempts, single use, request cooldown 30 seconds, access-token lifetime 30 minutes. Tokens belong to one service/institution. This is separate from any future Capital Insight user-login system.

Bank routes:

- GET `/v1/institution` (public).
- GET `/v1/accounts`, optionally `account_type`; returns an array.
- GET `/v1/accounts/{id}` and `/v1/accounts/{id}/balance`.
- GET `/v1/accounts/{id}/transactions?limit=10&offset=0&start_date=2026-08-01&end_date=2026-11-01&category=groceries`.
- Transaction response is `{ items, total, limit, offset }`, newest first. Limit 1-100; date bounds inclusive. Supported categories and account types are defined in mock_bank schemas.

Loan routes:

- GET `/v1/lender`, GET `/v1/loan-offers` (public).
- POST/GET `/v1/loan-applications`; GET `/v1/loan-applications/{id}`.
- GET `/v1/loans`, `/v1/loans/{id}`, `/v1/loans/{id}/schedule`.
- Example application: `{ "loan_type": "personal_loan", "amount": "10000.00", "term_months": 36, "annual_income": "72000.00", "existing_monthly_debt": "300.00", "credit_score": 720 }`.
- Supported types: personal_loan, auto_loan, mortgage. Use each offer's min/max and allowed terms, rather than assuming any term is valid.

Mortgage routes:

- GET `/v1/lender`, GET `/v1/mortgage-offers` (public).
- POST/GET `/v1/mortgage-applications`; GET `/v1/mortgage-applications/{id}`.
- GET `/v1/mortgages`, `/v1/mortgages/{id}`, `/v1/mortgages/{id}/schedule`.
- Example application: `{ "property_value": "350000.00", "down_payment": "70000.00", "term_months": 360, "annual_income": "120000.00", "existing_monthly_debt": "500.00", "credit_score": 740 }`.
- Financed amount is calculated by the service, not submitted as amount. The optional mortgage_type is only "mortgage". Down payment must be less than property value; terms are 180, 240, or 360 months.
- Responses add amount, loan_to_value, apr, monthly_payment, status, decision_reason, and identifiers. Status is approved or declined. Schedule rows include installment, due_date, payment, principal, interest, remaining_balance.
- Repayment previews omit taxes, insurance, PMI, escrow, and closing costs. Label payments as principal and interest.

Handle 401 (reauthorize), 404 (unavailable/not owned), 409 (declined application has no schedule), 422 (field/range validation), and 429 (cooldown). FastAPI errors use a detail field; validation detail may be an array. A successfully submitted but declined application still returns 201; inspect status rather than treating every 201 as approval.

Do not assume direct browser requests to these services will work: the current APIs do not configure browser CORS. For optional integration, use fixed, server-side upstream URLs through an appropriate Next.js adapter/Route Handler, or wait for the main backend. Keep tokens per session on the server; do not commit them or put them in public variables/localStorage. In live mode, validate authorization at every boundary and avoid shared caching of customer-specific responses.

## Future backend and AI handoff

The intended final flow is browser -> Capital Insight main backend -> mock institutions, with the main backend importing/normalizing records and returning aggregated data. The frontend should depend on its data interface, so that this future integration replaces the adapter rather than page layouts.

Insights and planning views should use clearly labeled sample output until Nemotron is connected by the backend. Do not send browser requests directly to an AI provider or invent a working AI endpoint. Any new proposed backend response shape should be recorded next to the frontend types and agreed with the backend developer.

## Validation before handing work back

From `frontend/`:

```powershell
npm run lint
npm run build
```

Verify the UI with the Python services stopped: navigation, responsive layouts, fixture connection flow, transaction filters/pagination, application approval/decline feedback, schedule display, loading/empty/error states, and keyboard access should work. Report any build failures caused by external font/network access honestly; do not claim successful validation without running it.

Do not add a testing framework solely for cosmetic changes. Add focused tests when financial calculations, provider transformations, or other meaningful logic warrant them. Keep changes scoped and document how to switch providers, what is mocked, and which integrations remain unavailable.

## Useful references

- `frontend/AGENTS.md` and installed `frontend/node_modules/next/dist/docs/` for this Next.js version.
- `services/mock_bank/README.md`, `services/mock_loan/README.md`, and `services/mock_mortgage/README.md` for setup and contracts.
- Official Next.js docs: https://nextjs.org/docs/app/getting-started/server-and-client-components and https://nextjs.org/docs/app/guides/environment-variables. Prefer the installed docs when version differences arise.


## Merged backend interfaces

The frontend's existing `/api/v1` routes and X-Session-Id authentication take priority for frontend integration. They remain compatible with the incoming http-provider and development launcher. The `/v1` application bearer-token routes independently preserve persistent users, encrypted connections, and Plaid support from the core API commit. Both interfaces run in the same app; their sessions and linked connections are separate. See backend/Readme.md for frontend-session setup and backend/CORE_API.md for persistent auth/Plaid. Do not substitute one interface's tokens or response shapes for the other.


## Verified email identity (supersedes earlier anonymous-linking guidance)

The current app signs users in at `/sign-in` by emailing their own inbox. Backend `/v1/auth/request-email-code` and `/verify-email-code` create/verify one normalized unique email identity. UUIDs remain foreign keys; no SSNs are used. Financial routes and Plaid require a verified user. Frontend `/api/v1` sessions bind to that user's app session and hydrate persisted mock connections from the same ownership database as `/v1`. Anonymous sessions can browse metadata but cannot connect accounts. Do not restore anonymous linking or the fixed-recipient sign-in behavior.

The Connections page supports Plaid Link; `/banks` shows Plaid accounts for the verified user. Plaid Sandbox uses test data; real bank access requires production configuration. Email alone must never authorize a real bank. Mock consent codes go to the signed-in user's verified address through MOCK_SERVICE_API_KEY-protected forwarding. Read EMAIL_SETUP.md for the current setup and additive schema upgrade.

## Independent institution verification (supersedes recipient forwarding above)

`MOCK_EMAIL_RECIPIENT_MODE=customer` is now the default. Each institution sends consent codes to its own database customer's email and verifies them itself. The core forwards only the institution email, then the returned code; no internal key or recipient override is sent. Institutions reject recipient overrides in customer mode. Configure each deployed service's SMTP credentials and database independently; the root `.env.mail` is only a local convenience. Legacy forwarding requires explicit `forwarded_demo` mode on both ends. See DISTRIBUTED_EMAIL.md and EMAIL_SETUP.md.

## Plaid and mock connections coexist

Frontend `/api/v1` requests send the app bearer as well as the adapter session cookie. The backend recovers adapter sessions from persistent user connections when its in-memory state is lost, returns the current adapter ID in `X-Session-Id`, and validates the app session before restoring any links. Do not show all providers as disconnected solely because an adapter cookie is stale. Expired institution consents still require reconnection.

HTTP account and overview pages combine mock accounts with Plaid snapshots. `plaid-normalize.ts` rounds Plaid amounts to cents using exact integer arithmetic for portfolio calculations; API snapshots retain original precision. The USD portfolio excludes unknown balances and other currencies; `/banks` shows all Plaid accounts. Opening balances and loan details unavailable from Plaid remain null. Plaid cached transactions are read separately from mock history. A successful Link exchange attempts transaction sync, and `/banks` provides a refresh action. Failures from a separate mock provider must not hide Plaid accounts on `/banks`.
