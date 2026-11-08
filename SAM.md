# Sam, goals and forecasts (NVIDIA Nemotron)

Sam is Capital Insight's finance-only assistant. The Plan & goals page holds the user's goals and preferences. Both require the core API and a verified sign-in.

## Enable Sam

1. Create a key at https://build.nvidia.com/ (it starts with `nvapi-`).
2. Put it in `backend/.env` (private and git-ignored). Never put it in the frontend or a `NEXT_PUBLIC_*` variable:

   ```dotenv
   NVIDIA_API_KEY=nvapi-...
   NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b
   ```

3. Restart the core API. In `frontend/.env.local` set `DATA_SOURCE=http` and `BACKEND_API_URL=http://localhost:8000`, then sign in.
4. Open **Ask Sam** and allow Sam to use your aggregated data. The opt-in is stored per user and can be turned off in Plan & goals → Customize.

Without a key, goals, sliders, forecasts and the subscription/overspending detectors still work. Sam shows a setup notice.

## What exists

| Area | Where |
| --- | --- |
| Goals (education, car, retirement, emergency, investment, credit, custom), preferences, forecast, Sam chat | `backend/app/routers/planning.py` → `/v1/planning/*` |
| Deterministic math (goal projection, credit-utilization payment plan) | `backend/app/planning_math.py` |
| Aggregated snapshot, subscription and overspending detection | `backend/app/financial_context.py` |
| Nemotron call, topic filter, output parsing | `backend/app/sam.py` |
| Frontend | `/planning` (`components/planning/planning-hub.tsx`), `/sam` (`components/planning/sam-chat.tsx`), Overview widgets (`components/dashboard/planning-widgets.tsx`) |

Overview shows only goals marked "Show on dashboard" and features the user switched on (forecast, subscriptions, spending check-in), and only in `DATA_SOURCE=http`.

## Design rules

- **The model never does the math.** Payments, projections and forecasts come from `planning_math.py` using Decimal. Sam explains those figures and may not change them.
- **No promises.** A credit-score target is an aspiration. Sam plans utilization and payments ("drop utilization to 30% → pay $X/month for 8 months") but never predicts a score, a return or an approval.
- **Minimal context.** The model receives an allowlisted aggregate: balances, APRs, limits, category totals, goal parameters and a synthetic score. It does not receive account numbers, emails, merchant names, goal names or tokens. Emails, long digit runs, SSN patterns and `nvapi-` keys are scrubbed from user text and from model output.
- **Finance only, three layers:**
  1. A regex pre-filter (`finance_request`) refuses off-topic or abusive prompts (prompt injection, role-play jailbreaks, fraud, creative writing) before any API call.
  2. The system prompt makes the model return `allowed:false` for anything else.
  3. After 3 refusals within 15 minutes, `/sam/chat` returns 429 and Sam stops responding for that user.
- **Rate limits:** 6 Sam requests per user per minute. Request IDs make retries idempotent.
- Thinking is disabled by default (`NVIDIA_ENABLE_THINKING=false`), and `<think>` content is never shown.

## Tests

`backend/tests/test_planning.py` mocks NVIDIA. It covers the math, goal ownership, opt-in/no-key states, the off-topic refusal and lockout, prose-wrapped JSON, and that no email or key is sent to the model.
