<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->


## Capital Insight frontend handoff

Read [the repository contributor guide](../AGENTS.md) before implementing the UI. It describes the product, current service contracts, suggested screens, fixture-first development, financial data conventions, and the future main-backend integration boundary.

The main backend is now implemented in `backend/` with Swagger at port 8000 by default; see `backend/Readme.md` for setup, authentication, aggregation, and Plaid. Keep deterministic local fixtures behind a typed data-provider interface so frontend development can continue without running Python services. Preserve the generated Next.js guidance above and follow the installed version's docs.
