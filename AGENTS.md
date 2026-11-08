# Rules for AI coding assistants (and humans)

Read this before changing code. It keeps AI-written code consistent with the rest of
the repo, so we can vibe code fast without breaking things.

## What this is
Capital Insight: one dashboard for all of a person's banks, with an AI coach (NVIDIA
Nemotron) that turns goals into plans. Three services plus a frontend:

| Folder | What | Port |
|---|---|---|
| `frontend/` | Next.js UI. Talks ONLY to core-api. | 3000 |
| `backend/` | core-api (FastAPI): aggregation, math engine, AI agent | 8000 |
| `mock-bank/` | Fake partner bank (FastAPI + SQLite). One codebase, run once per bank. | 9001, 9002 |

## Golden rules
1. **The LLM never does math.** Numbers come from pure functions in `backend/app/engine/`.
   The agent (`backend/app/agent/`) calls them as tools and explains the results.
2. **Raw external JSON stops at `backend/app/sources/`.** Map it to `app/domain/models.py`
   right there. The engine, agent, and routes only see domain models.
3. **Money:** `Decimal` in Python, integer cents in the mock-bank DB, decimal *strings*
   in JSON (`"600.00"`). Never `float` for money.
4. **Secrets live only in `.env` files** (git-ignored). Never in code, docs, commits,
   logs, or `NEXT_PUBLIC_*` variables. The browser never calls banks, Nessie, or NVIDIA.
5. **Validate every input with Pydantic** (types, lengths, patterns). Free text that goes
   to the LLM passes `reject_ssn` first.
6. **Routes are thin.** A route validates input, calls one engine/source function, and
   returns a Pydantic model. Business logic goes in `engine/`.
7. **Every engine function and every endpoint gets a test.** Run the tests after every change.
8. **No new dependency without a one-line reason** in the PR description.
9. **Small, single-purpose files.** If a file passes ~250 lines, split it.

## Commands
```bash
cd backend   && pytest -q && ruff check . && ruff format --check .
cd mock-bank && pytest -q && ruff check . && ruff format --check .
cd frontend  && npm run lint && npm run typecheck && npm test && npm run build
docker compose up --build        # backend services at once
```

## Recipes
- **New endpoint:** request/response models + route in `backend/app/api/routes.py` →
  logic in `engine/` → test in `backend/tests/` → regenerate frontend types.
- **New bank:** no code. Add a service in `docker-compose.yml` with a new `BANK_ID`,
  add accounts under that ID in `mock-bank/data/customers.json`, add it to `BANKS`.
- **New data source:** a new file in `backend/app/sources/` that maps to domain models,
  tested with `httpx.MockTransport` (see `tests/test_bank_api.py`).
- **New agent tool:** an args model + `Tool(...)` entry in `backend/app/agent/tools.py`
  that calls an engine function, plus a test in `tests/test_agent.py`.

## Frontend rules
- This is Next.js 16: read `frontend/node_modules/next/dist/docs/` before using an
  API you're unsure of (see `frontend/AGENTS.md`).
- API types are generated, never hand-written: `npm run gen:api` (backend running).
- All API calls go through `src/lib/api.ts` (openapi-fetch + `unwrap` for clear errors).
  Reads are SWR hooks in `src/lib/queries.ts`, one per endpoint.
- Money arrives as decimal strings. Format with `src/lib/format.ts`; never do money math
  in the frontend.
- Every data view has loading, empty, and error states (`src/components/states.tsx`).
- Colors come from the tokens in `src/app/globals.css` (light + dark). Status colors
  always come with an icon and a text label (`StatusMark`).

## Definition of done
Tests and lint pass, you clicked through it once in the browser or `/docs`, and the
PR description says what changed and how you tested it.
