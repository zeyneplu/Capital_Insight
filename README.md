# Capital Insight

One clear view of your whole financial life, across every bank, with an AI coach that
turns goals ("raise my credit score", "save for a house") into concrete monthly plans.
Built at HackUTD 2026.

## The idea in one picture

```
            Browser (Next.js, :3000)
                     │  JSON over HTTPS. The browser only ever talks to core-api.
                     ▼
        ┌──────────── core-api (FastAPI, :8000) ────────────┐
        │ api/      thin routes, input validation            │
        │ engine/   pure math: health, plans, forecasts      │──► NVIDIA Nemotron (agent)
        │ agent/    Nemotron loop that calls engine tools    │
        │ sources/  one client per data provider             │──► Capital One Nessie (GET)
        └──────┬───────────────────────────┬────────────────┘
               │ consent + Bearer token    │
     ┌─────────▼────────┐        ┌─────────▼────────┐          ┌──────────────┐
     │ mock-bank :9001  │        │ mock-bank :9002  │          │ Postgres     │
     │ BANK_ID=pecan    │        │ BANK_ID=comet    │          │ users, goals │
     │ SQLite           │        │ SQLite           │          └──────────────┘
     └──────────────────┘        └──────────────────┘
       same code, same image, different environment = different bank
```

We pretend banks have a Zelle-style partnership with us: each one exposes the same
API. A user connects a bank with email + last 4 of SSN, the bank emails a 6-digit
code, and the code becomes an access token. That is how real open banking (OAuth/FDX)
works, simplified.

## Run it

**Everything with Docker** (needs Docker Desktop):
```bash
cp backend/.env.example backend/.env       # then add your keys
docker compose up --build
```

**Or each service by hand** (faster reloads while coding), in 3 terminals:
```bash
# 1 and 2: two banks from the same code
cd mock-bank && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
uvicorn mockbank.main:create_app --factory --port 9001 --reload
BANK_ID=comet BANK_NAME="Comet Card (demo)" uvicorn mockbank.main:create_app --factory --port 9002

# 3: core-api
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
cp .env.example .env && uvicorn app.main:app --reload
```

Then open the interactive docs: core http://localhost:8000/docs, banks
http://localhost:9001/docs and http://localhost:9002/docs.

**Connect a bank by hand (great way to learn how APIs work):**
1. On http://localhost:9001/docs → `POST /v1/consents` with
   `{"email": "alex.rivera@example.com", "ssn_last4": "4821"}`
2. Read the "email": http://localhost:9001/dev/outbox
3. `POST /v1/consents/{consent_id}/token` with the code → copy `access_token`
4. Click **Authorize**, paste the token, then `GET /v1/accounts`

Demo people (synthetic): `alex.rivera@example.com` / `4821`, `jordan.lee@example.com` / `1937`.

## Tests
```bash
cd backend && pytest -q      # 62 tests
cd mock-bank && pytest -q    # 21 tests
cd frontend && npm test      # 6 tests (+ lint, typecheck, build in CI)
```

## Capital One (Nessie, read-only)
```bash
cd backend && source .venv/bin/activate
python -m scripts.nessie_check    # does our key have data? never prints the key
```
If it says ✅, set `DATA_SOURCE=nessie` in `backend/.env` and use the customer ID it prints.

## Frontend
```bash
cd frontend && npm install && cp .env.example .env.local
npm run dev        # http://localhost:3000 (backend must be running on :8000)
```
How screens get data, and the pattern for adding one: [frontend/README.md](frontend/README.md).

## Working on this repo
Read [AGENTS.md](AGENTS.md) first. It holds the rules for us and for AI coding tools.
