# Running Capital Insight with Docker Compose

One command starts the frontend, the core API and all six mock institutions.

| Service | Container | Host URL |
| --- | --- | --- |
| Frontend (Next.js standalone) | `web` | http://localhost:3000 (`WEB_PORT`) |
| Core API (FastAPI, Sam, Plaid) | `api` | http://localhost:8000 (`API_PORT`), docs at `/docs` |
| Chase / Amex / PNC / Discover mock banks | `chase` `amex` `pnc` `discover` | http://localhost:8001 – 8004 |
| Mock loans / mortgages | `loans` `mortgages` | http://localhost:8005 / 8006 |

All ports bind to `127.0.0.1` only. Containers reach each other by service name (`http://api:8000`, `http://chase:8000`, …).

## Prerequisites

- Docker Desktop running.
- `backend/.env` (from `backend/.env.example`) holding `ENCRYPTION_KEY`, `DATABASE_URL`, `NVIDIA_API_KEY` and optional Plaid keys.
- Optional, at the repository root: `.env.mail` (SMTP) and `.env.tester` (judge account). Compose reads both if present.

No secrets are baked into images. They are passed at runtime through `env_file`, and `.dockerignore` keeps every `.env*` file out of build contexts.

## Start

```powershell
docker compose up --build -d
docker compose ps                  # wait for "healthy"
```

If ports 3000 or 8000 are taken, pick others (the core API's CORS origin follows `WEB_PORT`):

```powershell
$env:WEB_PORT=3002; $env:API_PORT=8010; docker compose up --build -d
```

Stop the non-Docker launcher (`scripts/dev.py`) first; both use ports 8001–8006.

## Database

- **Core API → AWS RDS PostgreSQL** through `DATABASE_URL` in `backend/.env`. The image includes the public RDS CA bundle, so `DATABASE_SSLMODE=verify-full` works in the container. Container traffic leaves through your machine's public IP, so the RDS security group rule for your IP still applies. See backend/AWS_RDS.md.
- **Offline alternative:** a local PostgreSQL container instead of RDS:

  ```powershell
  docker compose -f compose.yaml -f compose.local-db.yaml up --build -d
  ```

- **Mock institutions** keep SQLite files in named volumes. The four banks share `bank_data`; loans and mortgages have `loan_data` and `mortgage_data`. The files are seeded on first start.

## Judge / tester account

With `.env.tester` present (see TESTER_ACCESS.md):

```powershell
docker compose run --rm seed
```

This copies synthetic accounts into the mock volumes, saves goals and preferences, and links all six institutions with the tester code. It is safe to rerun; rerun it before judging to refresh the 12-hour consents.

## Real users on fresh volumes

Mock institutions only email consent codes to customers they know, and they stay silent for unknown emails so they don't reveal who has an account. New Docker volumes contain only the synthetic seed customers. Register each real user's email once per set of volumes:

```powershell
docker compose run --rm --no-deps seed python scripts/add_demo_customer.py --email you@example.com
```

## Everyday commands

```powershell
docker compose logs -f api                 # core API logs
docker compose logs -f chase               # consent codes appear here in DEMO_MODE
docker compose up --build -d api web       # rebuild after code changes
docker compose restart api                 # pick up backend/.env changes
docker compose down                        # stop; volumes keep mock data
docker compose down -v                     # stop AND delete mock data volumes (RDS is untouched)
```

## Notes

- The frontend reads `DATA_SOURCE` and `BACKEND_API_URL` at request time, so one image works against any core API.
- Non-Docker development (`python scripts/dev.py`, `npm run dev`) is unchanged. The older per-service compose files under `backend/` and `services/*/` still work for running parts on their own.
