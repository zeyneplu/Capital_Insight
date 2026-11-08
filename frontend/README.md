# Capital Insight: frontend

Next.js 16 (App Router) + TypeScript + Tailwind 4. Talks only to core-api (`backend/`).

## Run it
```bash
# 1. The backend must be running (see the root README): http://localhost:8000
# 2. Then, in this folder:
npm install
cp .env.example .env.local
npm run dev            # http://localhost:3000
```

## How a screen gets its data
```
page.tsx ──calls──► useHealthReport(id)        src/lib/queries.ts   (SWR hook: loading / error / data)
                        └─► api.GET(...)        src/lib/api.ts       (typed fetch, friendly errors)
                              └─► HTTP GET http://localhost:8000/api/v1/customers/{id}/health-report
                                    └─► JSON back ─► component renders it
```
Open DevTools → **Network** while the page loads to watch each request and its JSON.

## Add a new screen (the pattern)
1. **Backend first:** make sure the endpoint exists in http://localhost:8000/docs.
2. `npm run gen:api` to regenerate `src/lib/api-types.ts` (backend running). Never edit that file by hand.
3. Add a hook to `src/lib/queries.ts` (copy an existing one). For a form that *sends* data
   (POST), call `unwrap(api.POST(...))` from an event handler instead of a hook.
4. Build the component in `src/components/`, with **loading, error, and empty** states
   (`Skeleton`, `ErrorNotice`, `Empty` in `states.tsx`).
5. Show numbers exactly as the backend sends them, formatted with `src/lib/format.ts`.
   Never do money math in the frontend.

## Checks (CI runs all of these)
```bash
npm run lint && npm run typecheck && npm test && npm run build
```

## Files
| Path | What |
|---|---|
| `src/app/page.tsx` | Dashboard page |
| `src/components/` | Summary, health list, spending bars, accounts, status icons, states |
| `src/lib/api.ts` | The one API client + error messages |
| `src/lib/queries.ts` | Data hooks (one per endpoint) |
| `src/lib/insights.ts` | Turns indicators into plain-English sentences (+ tests) |
| `src/lib/format.ts` | Money, percent, date formatting |
| `src/app/globals.css` | Color and type tokens (light + dark) |
