# CLAUDE.md

Capital Insight is a HackUTD 2026 financial-wellness app with a Next.js frontend, a FastAPI core API, mock bank/loan/mortgage services, and Sam, a finance assistant on NVIDIA Nemotron.

**Read `AGENTS.md` first.** It is the authoritative contributor guide. Later sections there supersede earlier ones. When working in `frontend/`, also read `frontend/AGENTS.md` and the installed Next.js docs in `frontend/node_modules/next/dist/docs/`, because this Next.js version (16, Cache Components) differs from older APIs.

## Layout

- `frontend/`: Next.js App Router (`app/`, `components/`, `lib/`). Pages call `lib/data` (fixture or HTTP provider) or server actions in `lib/actions/`. Never fetch from JSX.
- `backend/app/`: core API on PostgreSQL (AWS RDS; see `backend/AWS_RDS.md`). SQLite there is only a local/test fallback. `/api/v1` is the frontend session adapter. `/v1` covers app auth, connections, Plaid, credit score and planning/Sam.
- `services/mock_bank|mock_loan|mock_mortgage/`: independent synthetic institutions. Preserve their API contracts.
- Feature docs: `DOCKER.md`, `TESTER_ACCESS.md`, `SAM.md`, `CREDIT_SCORE.md`, `TRANSACTIONS.md`, `PLAID_SETUP.md`, `EMAIL_SETUP.md`, `DISTRIBUTED_EMAIL.md`.

## Commands (Windows; repo venv at `.venv`)

```powershell
# whole stack in Docker (see DOCKER.md)
docker compose up --build -d
docker compose run --rm seed         # judge/tester account
# backend tests (point --basetemp at a writable folder if the default temp folder is locked)
.venv\Scripts\python.exe -m pytest backend/tests -q
# frontend
cd frontend; npm ci; npm run dev     # http://localhost:3000
npm run build                        # type-checks too
npm run lint
npm test                             # node --test on lib/**/*.test.ts (needs Node >= 22.18)
```

## Non-negotiables

- Money is a decimal string at boundaries. Calculate with Decimal (Python) or integer cents (TS), never floats. Rates are fractions ("0.0625" = 6.25%).
- Secrets (`NVIDIA_API_KEY`, Plaid, encryption key, upstream tokens) stay in `backend/.env` and server-side code. Never use `NEXT_PUBLIC_*`, never commit them, and never put them in a model prompt.
- Never silently replace a failed live request with fixtures. Label demo and synthetic data.
- Sam answers personal-finance questions only. Keep the pre-filter, model refusal and misuse lockout in `backend/app/sam.py` and `routers/planning.py`. Deterministic math lives in `planning_math.py`. The LLM explains numbers and never invents or guarantees them (no score, return or approval promises).
- No real payments, transfers or loan funding. Mock-bank postings are simulations (see `TRANSACTIONS.md`).
- Add focused tests for financial math, provider transformations and AI guardrails. Mock NVIDIA in tests and never call the live API from the test suite.
- Tester access (`.env.tester`) is one email, development-only, opt-in. Keep it that way.
