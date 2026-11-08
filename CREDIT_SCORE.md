# One current synthetic credit profile

Each mock bank, credit-card provider, loan service, and mortgage service stores `customers.credit_score` and `customers.credit_score_as_of`. Scores belong to a customer, not an account, card, transaction, or property. The same normalized customer email receives the same synthetic-credit-v1 value on every independently deployed mock service. No SSN, credit bureau, or external scoring API is involved.

Each service vendors the same versioned synthetic policy so its existing standalone deployment continues to work. Policy changes must be applied to all three service implementations and the fixture policy together. The current score is fictional, stable, and generated for testing; it does not predict creditworthiness. The UI explicitly labels it as synthetic and uses app-defined demo labels, not FICO or VantageScore branding.

Startup adds the profile columns to existing service databases and reconciles current profiles without dropping customers or financial records. New customers receive the same policy automatically. To upgrade/reconcile all six active local mock databases and the core's cached customer payloads explicitly:

```powershell
.\.venv\Scripts\python.exe scripts/sync_demo_credit.py
```

Backups and obsolete database files are excluded. Restart the APIs after upgrading code. Customer profiles returned by authenticated `/v1/customers/me` include:

```json
{
  "email": "alice@example.test",
  "credit_score": 762,
  "credit_score_as_of": "2026-11-08"
}
```

This is a partial example of the existing customer payload; other customer fields remain present.

## Core API and consent

Authenticated `GET /v1/credit-score` requires verified app sign-in. It fetches fresh customer profiles using active mock-bank consents, returns a single score with provider names and its as-of date, and maintains at most one `credit_profiles` row per app user (`user_id` is the primary key). For example:

```json
{
  "score": 762,
  "minimum": 300,
  "maximum": 850,
  "model": "Synthetic demo score v1",
  "synthetic": true,
  "as_of": "2026-11-08",
  "sources": ["Chase Mock Bank", "Discover Mock Bank"],
  "status": "available"
}
```

Scores are never averaged, added together, or separately displayed per bank. Different emails can represent different customers; the core does not rewrite an institution's customer identity to make it match an app login. If reports conflict, the response withholds the score with `conflicting_profiles`. Use the same registered customer email when linking this demo user's institutions. With no active mock-bank consent, the response is `connect_bank` and exposes no cached score. If all authorized providers fail, it is `unavailable` rather than a fabricated value.

Plaid account and transaction data do not provide this mock credit profile, so a Plaid-only connection does not produce a credit score. Loan/mortgage-only connections do not enable the bank score card, although their borrower databases maintain the same current profile policy.

The Overview page shows one score card when a bank is connected, with its range, demo rating, update date, and sources. Fixture mode also displays one score for its explicitly fictional session owner.

## Historical application inputs

Loan and mortgage application `credit_score` fields already existed. They record a self-reported input at application time, not today's customer profile. Existing inputs, decisions, APRs, and schedules are preserved; changing historical inputs would misrepresent the decision. The application detail UI labels them **Credit score at application (self-reported)**. Newly provisioned demo application copies use their new customer's synthetic score. No credit check is performed.
