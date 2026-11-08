# Judge / tester access

A single documented tester account lets judges sign in and link every mock institution without access to a real inbox.

| | |
| --- | --- |
| Email | value of `TESTER_EMAIL` in `.env.tester` (default `test@email.com`) |
| Code | value of `TESTER_CODE` in `.env.tester` (six digits) |

`.env.tester` lives at the repository root, is git-ignored, and is read by `scripts/dev.py`, which passes both values to the core API and all six mock services. Delete the file (or remove a value) and restart to disable tester access.

## Safeguards

- **Development only.** The core API ignores tester settings when `ENVIRONMENT=production`. The mock services honor them only with `DEMO_MODE=true`.
- **One email only.** Every other user still receives random emailed codes.
- **Normal code rules still apply.** The UI must request a code first; it expires after 5 minutes, allows 5 attempts and works once. No email is sent for the tester account.
- **Longer consent for the tester only.** Mock institution consents for the tester last `TESTER_TOKEN_TTL_SECONDS` (default 12 hours) so links survive a judging session; everyone else keeps 30 minutes.
- **Synthetic data only.** The account holds fictional data. `@email.com` is a real domain, so the tester address is never emailed.

## Prepare the account

With the stack running (`python scripts/dev.py`):

```powershell
.venv\Scripts\python.exe scripts\seed_tester.py --api http://localhost:8000
```

This is idempotent. It copies the standard synthetic accounts and transactions into each mock institution, saves sample goals and dashboard preferences, and links all six institutions with the tester code. Rerun it before judging if the 12-hour consents have expired.

## Judge flow

1. Open the app → **Sign in** → enter the tester email → enter the tester code.
2. Overview shows balances, the synthetic credit score, goals, a forecast and spending check-ins.
3. Plan & goals and Ask Sam use the same linked data. To show the linking flow, open Connections, reconnect any institution with the same email and code.
