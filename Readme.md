# Capital Insight

HackUTD 2026 financial wellness app: one dashboard for your bank accounts, cards, loans and mortgage.

```text
browser ──► frontend (Next.js :3000) ──► core API (FastAPI :8000) ──► mock banks :8001-8004, mock loans :8005, mock mortgages :8006
```

| Folder | What | Docs |
| --- | --- | --- |
| `frontend/` | Next.js UI. Demo fixtures by default; `DATA_SOURCE=http` uses the core API | [frontend/Readme.md](frontend/Readme.md) |
| `backend/` | Core API: sessions, server-side bank tokens, aggregation | [backend/Readme.md](backend/Readme.md) |
| `services/` | Synthetic bank, loan and mortgage APIs | `services/*/README.md` |
| `scripts/dev.py` | Starts the whole stack in one command | below |

## Quick look (demo data, Node.js only)

```bash
cd frontend && npm ci && npm run dev
```

Open http://localhost:3000. Use the fixture consent code `424242`.

## Run everything (live services)

Needs Python 3.10+ and Node.js 20.9+. One-time setup from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r services/mock_bank/requirements.txt -r backend/requirements.txt
(cd frontend && npm ci)
```

Then, every time:

```bash
python scripts/dev.py
```

This starts the six mock services, the core API and the frontend, already wired together. Open
http://localhost:3000 → **Connections**. When you request a code, the launcher prints it, for example
`>>> chase: code for customer1@chase.example.test is 123456`. Ctrl+C stops everything. Logs are in `logs/`.

Demo emails: `customer1@<id>.example.test`, where `<id>` is `chase`, `amex`, `pnc`, `discover`, `loans` or
`mortgages`.

## Tests

```bash
cd frontend && npm test && npm run lint
cd backend && pytest -q
cd services/mock_bank && pytest -q      # same for mock_loan and mock_mortgage
```

Read [AGENTS.md](AGENTS.md) before contributing.
