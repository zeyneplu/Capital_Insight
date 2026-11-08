# Core API on AWS RDS for PostgreSQL

The core API (users, sessions, encrypted institution connections, Plaid cache, credit profiles, goals and Sam chat history) uses PostgreSQL. AWS RDS is the managed option. The mock institutions (`services/mock_*`) keep their own SQLite files and do not change.

SQLite remains a local fallback for tests and offline work. `ENVIRONMENT=production` refuses to start without a PostgreSQL `DATABASE_URL`.

## 1. Create the database (AWS console)

RDS → **Create database**:

| Setting | Value |
| --- | --- |
| Creation method | Standard create |
| Engine | PostgreSQL 16 (or newer) |
| Template | Free tier / Dev-Test for the hackathon; Production for real users |
| DB instance identifier | `capital-insight` |
| Master username | `capital_admin` |
| Credentials | Self-managed password. Generate a strong one and store it in your password manager. |
| Instance class | `db.t4g.micro` (enough for a demo) |
| Storage | 20 GiB gp3; storage autoscaling optional |
| Connectivity | See step 2 |
| Additional configuration → Initial database name | `capital_insight` (otherwise only `postgres` exists) |
| Backups / encryption | Keep automated backups and encryption at rest enabled |

Free-tier eligibility depends on your account. Instances, storage and backups bill hourly, so delete the instance when the hackathon is over.

## 2. Network access

**Backend running on your laptop (hackathon):**
- Set *Public access* to **Yes**.
- Edit the instance's VPC security group with one inbound rule: PostgreSQL (TCP 5432), source **My IP**.
- Never use `0.0.0.0/0`. Update the rule when your IP changes.

**Backend deployed in AWS (ECS, EC2, App Runner, Lambda):**
- Set *Public access* to **No** and put the database in the same VPC.
- Allow 5432 only from the backend's security group.

## 3. Configure the core API

After the instance shows *Available*, copy the **Endpoint** from Connectivity & security. Then edit `backend/.env` (git-ignored; never commit it):

```dotenv
DATABASE_URL=postgresql+psycopg://capital_admin:URL_ENCODED_PASSWORD@capital-insight.xxxxxxxx.us-east-1.rds.amazonaws.com:5432/capital_insight
```

URL-encode special characters in the password, for example `@` → `%40`, `:` → `%3A`, `/` → `%2F`, `#` → `%23`. The command below prints an encoded value:

```powershell
.venv\Scripts\python.exe -c "import urllib.parse,getpass; print(urllib.parse.quote(getpass.getpass('RDS password: '), safe=''))"
```

### TLS

Connections to `*.rds.amazonaws.com` automatically use `sslmode=require`, so traffic is encrypted. To also verify the server's identity, which is recommended:

```powershell
mkdir backend\certs
curl.exe -o backend\certs\global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

Then add to `backend/.env`:

```dotenv
DATABASE_SSLMODE=verify-full
DATABASE_SSLROOTCERT=certs/global-bundle.pem
```

Optional pool tuning: `DATABASE_POOL_SIZE` (default 5), `DATABASE_MAX_OVERFLOW` (5), `DATABASE_POOL_RECYCLE_SECONDS` (1800), `DATABASE_CONNECT_TIMEOUT_SECONDS` (10). A `db.t4g.micro` instance allows roughly 80 connections, so keep the pool size × number of API processes well below that.

## 4. Move existing local data (optional)

Tables are created automatically on first start. To keep accounts, linked connections, goals and Sam chats from `backend/data/capital_insight.db`:

```powershell
.venv\Scripts\python.exe scripts\migrate_core_to_postgres.py --dry-run   # row counts only
.venv\Scripts\python.exe scripts\migrate_core_to_postgres.py
```

The script copies every table in one transaction, verifies the row counts, and refuses to write into a non-empty database. **Keep `ENCRYPTION_KEY` unchanged.** Saved institution tokens are copied encrypted and can only be decrypted with the same key. Keep the SQLite file as a backup until the app works against RDS.

## 5. Start and verify

Restart the core API (`python scripts/dev.py`). `GET /health` runs `SELECT 1` against the database, so a 200 response means the API reached RDS. If startup fails:

- **timeout:** the security group or public-access setting is blocking you, or your IP changed.
- **password authentication failed:** wrong user, or the password isn't URL-encoded.
- **database "capital_insight" does not exist:** you skipped *Initial database name*. Connect and run `CREATE DATABASE capital_insight;`.
- **certificate verify failed:** check `DATABASE_SSLROOTCERT` and use the RDS endpoint hostname, not an IP address.

## Running the tests against PostgreSQL

Use a **separate, disposable** database, because tests drop every table:

```sql
CREATE DATABASE capital_insight_test;
```

```powershell
$env:CORE_TEST_DATABASE_URL = "postgresql+psycopg://capital_admin:...@<endpoint>:5432/capital_insight_test"
.venv\Scripts\python.exe -m pytest backend/tests -q
```

Tests without the variable use temporary SQLite files.
