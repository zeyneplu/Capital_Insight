"""Does our Nessie key have usable data? One command, read-only, prints a verdict.

    cd backend && source .venv/bin/activate
    python -m scripts.nessie_check

Reads NESSIE_BASE_URL and NESSIE_API_KEY from backend/.env. Never prints the key.
If the field names it prints differ from what app/sources/nessie.py expects, that file
is the only place to fix.
"""

import asyncio
import sys
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.domain.errors import NotFoundError
from app.engine import cashflow, indicators
from app.sources.nessie import NessieError, NessieSource

KINDS = ("purchases", "deposits", "withdrawals", "bills", "loans")


async def main() -> int:
    settings = get_settings()
    if not settings.nessie_api_key:
        print("❌ NESSIE_API_KEY is empty in backend/.env")
        return 2
    key = settings.nessie_api_key.get_secret_value()
    print(f"Base URL: {settings.nessie_base_url}  (key: ****{key[-4:]})\n")

    async with httpx.AsyncClient(base_url=settings.nessie_base_url, timeout=15) as http:
        source = NessieSource(http, key)

        async def get(path: str):
            resp = await http.get(path, params={"key": key})
            return resp.status_code, (resp.json() if resp.content else None)

        try:
            status, customers = await get("/customers")
        except httpx.HTTPError as exc:
            print(f"❌ Can't reach Nessie ({exc.__class__.__name__}). Check NESSIE_BASE_URL.")
            return 2
        if status in (401, 403):
            print(f"❌ HTTP {status}: the key was rejected. Re-copy it from the Nessie portal.")
            return 2
        if status != 200 or not isinstance(customers, list):
            print(f"❌ Unexpected answer from /customers: HTTP {status}")
            return 2

        print(f"Customers visible to this key: {len(customers)}")
        if not customers:
            print(
                "\n⚠️  No data. GET-only means we can't create any ourselves.\n"
                "   → Ask the Capital One mentors for a key with seeded data.\n"
                "   → Until then, demo with DATA_SOURCE=fixtures and the mock banks."
            )
            return 1

        shown_fields: set[str] = set()
        best: tuple[int, str] | None = None
        for customer in customers[:3]:
            cid = str(customer["_id"])
            name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            _, accounts = await get(f"/customers/{quote(cid, safe='')}/accounts")
            accounts = accounts if isinstance(accounts, list) else []
            print(f"\n• {name or '(no name)'}  id={cid}  accounts={len(accounts)}")
            records = 0
            for acct in accounts:
                aid = str(acct["_id"])
                counts = []
                for kind in KINDS:
                    _, rows = await get(f"/accounts/{quote(aid, safe='')}/{kind}")
                    rows = rows if isinstance(rows, list) else []
                    records += len(rows)
                    counts.append(f"{kind}={len(rows)}")
                    if rows and kind not in shown_fields:  # show each shape once
                        shown_fields.add(kind)
                        print(f"    {kind} fields: {sorted(rows[0])}")
                print(f"  - {acct.get('type')}: balance={acct.get('balance')}  {' '.join(counts)}")
            if best is None or records > best[0]:
                best = (records, cid)

        assert best is not None
        print(f"\nRunning the full Capital Insight pipeline on customer {best[1]}…")
        try:
            profile = await source.get_profile(best[1])
            flow = cashflow.summarize(await source.get_transactions(best[1]))
        except (NessieError, NotFoundError) as exc:
            print(f"❌ Pipeline failed: {exc}")
            return 2
        for ind in indicators.health_report(profile).indicators:
            print(f"  {ind.label:32} {ind.value!s:>10}  {ind.status}")
        print(f"  Monthly income / spending        {flow.monthly_income} / {flow.monthly_spending}")
        print(f"  Sandbox credit score             {profile.credit_score}")

        if best[0] == 0:
            print("\n⚠️  Customers exist but have no transactions: dashboards will look empty.")
            return 1
        print(
            f"\n✅ Usable. In backend/.env set DATA_SOURCE=nessie, then try\n"
            f"   http://localhost:8000/api/v1/customers/{best[1]}/health-report"
        )
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
