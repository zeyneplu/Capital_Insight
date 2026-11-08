# Test Plaid Link locally

The backend creates Link tokens, exchanges public tokens, encrypts access tokens, reads accounts, and synchronizes transactions. The frontend starts Plaid Link from Connections and shows authorized accounts at `/banks`. Verified app sign-in is required. Plaid does not use the mock service API key or your Gmail SMTP password.

## Add only your two Plaid credentials

Create or sign in to your [Plaid Dashboard](https://dashboard.plaid.com/) and open [API keys](https://dashboard.plaid.com/developers/keys). Copy the client ID and **Sandbox** secret into the private `backend/.env`:

```dotenv
PLAID_CLIENT_ID=6af0434a8ce3c8000dfd0df4
PLAID_SECRET=778b88a8d03d02da286df11aae6dbc
PLAID_ENVIRONMENT=sandbox
PLAID_PRODUCTS=["transactions"]
PLAID_COUNTRY_CODES=["US"]
PLAID_REDIRECT_URI=
```

The other values are already prepared. Keep the existing `ENCRYPTION_KEY` unchanged so saved connections remain decryptable. Do not copy the example over your existing file. Keep keys in the backend environment; do not put them in chat, frontend variables, or Git.

Restart the running core API after saving. If restarting the whole stack yourself, stop the current stack first, then run from the repository root:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/dev.py --api-port 8007 --web-port 3001
```

## Connect a Sandbox institution

1. Open http://localhost:3001/sign-in and verify your email.
2. Open http://localhost:3001/connect and select **Connect a bank with Plaid**.
3. Choose a Sandbox institution. For its test credential flow, use username `user_good` and password `pass_good`. If that flow requests institution MFA, use `1234`. Some Link flows first offer a phone-number step; follow the Sandbox instructions shown there or skip it.
4. Complete account selection and consent. The app exchanges the returned public token on the backend and opens http://localhost:3001/banks.

These are Plaid's [official Quickstart test credentials](https://github.com/plaid/quickstart#test-credentials). Sandbox returns test data, not your real bank balance. Your Capital Insight email-code login remains separate from the Sandbox bank login.

The backend also provides authenticated `/v1/plaid/connections/{connection_id}/sync` and `/transactions` endpoints. Linking attempts an initial transaction sync; use **Refresh accounts and transactions** on `/banks` while Plaid prepares history. The main Accounts and Overview pages combine Plaid and mock data. Their USD totals include known USD balances, rounded to cents using exact decimal arithmetic; `/banks` displays all Plaid account snapshots. Missing opening balances remain unavailable rather than being invented.

Saved institution connections survive core restarts. The frontend supplies the persistent app bearer to recover a stale adapter session. Linking Plaid does not remove mock consents. Institution tokens still expire independently; reconnect an expired mock consent when needed.

Production bank access requires the appropriate Plaid access and configuration. Test the Sandbox flow first; do not enter real bank credentials into a Sandbox test flow.
