# Capital Insight frontend

Next.js App Router UI for Capital Insight (HackUTD 2026). It runs entirely on
deterministic demo fixtures, so **no Python services or backend need to be
running**. Read [`../AGENTS.md`](../AGENTS.md) for the product brief and service contracts.

## Run it (PowerShell or bash)

```powershell
cd frontend
npm ci
npm run dev        # http://localhost:3000
```

| Script | What it does |
| --- | --- |
| `npm run dev` | Development server |
| `npm run build` / `npm start` | Production build / serve it |
| `npm run lint` | ESLint |
| `npm test` | Finance and fixture tests (Node's built-in runner; needs Node 22.18+ for TypeScript type stripping) |

No `.env.local` is required. See [`.env.example`](.env.example) for the optional settings.

## Demo walkthrough

1. **Overview** (`/`): net worth, assets, liabilities, 30-day spending, cash flow, upcoming payments.
2. **Accounts** (`/accounts`): filter by type; open an account for details, category/date filters and pagination.
3. **Connections** (`/connect`): Discover starts disconnected. Connect it with the demo email shown and the
   **fixture-only code `424242`**. That code never works against the live mock services (they print a random
   code in their own server logs). Cooldown (30 s), 5 attempts and 5-minute expiry are simulated.
4. **Loans / Mortgages**: submit simulated applications. Try credit score `600` (declined), amount `999`
   (outside the product range), or a 2.5% down payment (declined). Approved records link to a full schedule.
5. **Insights** (`/insights`): clearly labeled sample insights from fixed rules, not AI.
6. **Reset demo session** (footer) restores the starting state.

## Architecture

```text
app/                 routes: static shell + <Suspense> around every data read
components/          ui/ (cards, badges, alerts, forms, pagination), charts/, feature folders
lib/
  types.ts           Raw* service shapes + view models (+ PROPOSED backend shapes)
  format.ts          USD, percent and date formatting (UTC, exact decimal strings)
  finance/           pure, framework-free math: money, amortization, underwriting, portfolio, insights
  data/
    provider.ts      the DataProvider interface every page uses
    index.ts         picks the provider from DATA_SOURCE (server only)
    mock-provider.ts fixtures + session-local demo state
    http-provider.ts placeholder for the future backend (fails loudly)
    normalize.ts     raw service JSON -> view models (shared by both providers)
    session.ts       httpOnly cookie for demo connections/applications
    fixtures/        raw-shaped records for banks, lender, mortgage lender
  actions/           Server Actions (the only code that writes the session)
```

Pages never import fixtures or fetch URLs: they call `getDataProvider()`. Fixtures are stored in the exact
JSON shape the mock services return and go through the same `normalize.ts` an HTTP adapter will use, so
connecting the backend replaces the provider, not the pages.

### Next.js 16 specifics worth knowing

- `cacheComponents` and `partialPrefetching` are on. Anything that reads cookies, `params` or
  `searchParams` sits inside `<Suspense>`, so each route prerenders a static shell and streams its data
  (the build marks them ◐ Partial Prerender).
- The sidebar's `usePathname` is wrapped in `<Suspense>` with a non-highlighted fallback; without it the
  build fails on routes with unknown dynamic params.
- `error.tsx` receives `error: unknown` and `retry()`. In production, server error messages are replaced by
  a digest, so the error UI gives guidance instead of echoing messages.
- After a streamed shell is sent, `notFound()` inside Suspense renders the not-found UI but cannot change
  the HTTP status from 200.

## Financial data rules (and where they are enforced)

- Money stays a decimal string at every boundary. Arithmetic uses integer cents as `bigint`
  (`lib/finance/money.ts`); `Intl.NumberFormat` formats the strings exactly.
- Payment, schedule and decision logic mirrors the Python services and is checked against golden values
  produced by running the real service code (`lib/finance/golden/`, regenerate with `generate_golden.py`).
- Balances are derived from opening balance + transactions; tests prove every balance reconciles, no asset
  overdraws, cards stay under limits, and dashboard totals equal their parts.
- No double counting: bank loans (PNC auto, Discover personal) come from mock_bank; the personal loan and the
  mortgage are lender records; there is no bank mortgage account. Spending excludes paychecks, transfers
  and debt payments. Property value is not an account, so net worth excludes it (and says so).
- Lender APIs expose the financed amount and a projected schedule only. The dashboard uses a labeled
  **fixture servicing snapshot** for the seeded loan and mortgage; applications approved during a demo
  session are shown as "Simulated · not funded" and never counted as debt.
- Nothing is presented as overdue: the snapshot date is fixed at Nov 1, 2026 and labeled everywhere.

## Switching data sources

| `DATA_SOURCE` | Behavior |
| --- | --- |
| unset / `mock` | Fixtures (default) |
| `http` | The core API in `backend/` (set `BACKEND_API_URL`). If it or a bank fails, the error page is shown; it never falls back to fixtures. Set it in `.env.local` before `npm run build`, because the demo banner is prerendered. |
| anything else | Configuration error |

`DATA_SOURCE` and `BACKEND_API_URL` are read on the server only.

## What is simulated, and persistence limits

- Connections, pending consent codes and submitted applications live in one httpOnly cookie in this
  browser for up to 7 days (5 most recent applications per lender). The cookie is validated on every read,
  and decisions are recomputed from the stored inputs, never trusted from the cookie.
- No real sign-in, payments, transfers or loan funding exist anywhere in the UI.

## Not available yet

- Capital Insight user login (core API sessions are anonymous and in memory).
- Live calls to the mock services (they do not enable CORS; integrate server-side through the backend or a
  Route Handler).
- AI analysis: Insights shows sample rule-based output until the backend provides Nemotron results.
- Proposed response shapes for the backend (`Dashboard`, `InsightReport` in `lib/types.ts`) still need to be
  agreed with the backend developer.
