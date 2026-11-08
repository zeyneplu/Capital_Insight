# Capital Insight core API

FastAPI service between the frontend and the mock institutions in `services/`:

```text
browser ──► Next.js server ──X-Session-Id──► core API (:8000) ──Bearer token──► mock_bank ×4, mock_loan, mock_mortgage
```

What it does, and nothing more yet:
- **Sessions.** `POST /api/v1/sessions` returns an opaque id. The frontend server keeps it in an httpOnly cookie.
- **Consent and token custody.** It proxies each service's request-code/verify-code flow and keeps the access
  tokens server-side, so they never reach the browser. An upstream 401 drops that connection.
- **Aggregation.** Accounts and transactions are fetched from every connected bank in parallel. Failures are
  returned as an explicit `errors` list, never silently omitted.
- **Lending.** Offers, applications and schedules for the loan and mortgage lenders. Each lender's own schema
  is the authority, and its 422 responses pass through.

Responses keep the services' raw JSON shapes (decimal strings for money). The frontend normalizes them with
the same code it uses for fixtures.

## Run (Python 3.11+)

Start the services you want first (see `services/*/README.md`, with `DEMO_MODE=true`). Then, from `backend/`:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs. Service URLs are configurable; see `.env.example`.
Institutions that aren't running simply fail when you connect to them.

To point the frontend at it, put this in `frontend/.env.local` and restart `npm run dev`:

```dotenv
DATA_SOURCE=http
BACKEND_API_URL=http://localhost:8000
```

Codes are never emailed. Copy the `DEVELOPMENT ONLY` code from the service's terminal log.

## Endpoints (`/api/v1`, all but sessions/offers need `X-Session-Id`)

| Method | Path | |
| --- | --- | --- |
| POST | `/sessions` | new session |
| GET | `/institutions` | institutions + connection status + customer |
| POST | `/institutions/{id}/request-code` · `/verify-code` | consent flow (429/401/422 pass through) |
| DELETE | `/institutions/{id}/connection` | disconnect |
| GET | `/accounts?account_type=` | accounts from all connected banks `{items, errors}` |
| GET | `/accounts/{id}` · `/accounts/{id}/transactions` | owner bank is found automatically |
| GET | `/transactions` | every transaction of every connected account (dashboards) |
| GET | `/lenders/{loans\|mortgages}/offers` · `/applications` | `applications` returns `{connected, items}` |
| POST | `/lenders/{id}/applications` | submit (201 can still be `declined`) |
| GET | `/lenders/{id}/applications/{appId}/schedule` | `{kind: schedule \| declined \| not_found}` |

## Tests

```bash
pytest -q
```

The tests use a fake upstream (`httpx.MockTransport`), so no services are needed. They cover token custody,
expired consents, ownership lookup, partial failures, pagination and unsafe IDs.

## Known limits

- Sessions live in memory: they are lost on restart and not shared across processes. Move them to
  PostgreSQL or Redis next.
- The frontend-compatible /api/v1 interface uses anonymous sessions. The independent /v1 interface supports persistent user login and Plaid; see CORE_API.md.
- No AI endpoints yet. The frontend's Insights page still shows labeled sample rules.


## Persistent accounts and Plaid

The same server also exposes the `/v1` API from the core API implementation. It provides application registration/login, encrypted provider connections, aggregated snapshots, and Plaid Sandbox linking and transaction sync. Its dependencies and database configuration are included in this merged backend.

Read [CORE_API.md](CORE_API.md) for `.env` setup, PostgreSQL/Docker configuration, Plaid credentials, and a full walkthrough. You may continue using `python scripts/dev.py` from the repository root for the frontend's anonymous-session experience. The default development database is backend/data/capital_insight.db. No Plaid keys are required for the existing mock frontend.

`X-Session-Id` authorizes `/api/v1`; an application `Authorization: Bearer ...` token authorizes `/v1`. The connection stores are separate. The frontend continues to use `/api/v1` and does not gain Plaid data automatically; its provider must explicitly integrate `/v1` when that feature is added.
