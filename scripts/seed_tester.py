"""Prepare the judge/tester account so the dashboard has data to show.

    python scripts/seed_tester.py                       # uses .env.tester, API on :8000
    python scripts/seed_tester.py --api http://localhost:8010

Requires the stack running via scripts/dev.py with a .env.tester file (TESTER_EMAIL, TESTER_CODE).
Steps (all idempotent, synthetic data only):
  1. Copies the standard synthetic accounts, transactions and applications into each mock
     institution for TESTER_EMAIL (scripts/add_demo_customer.py).
  2. Saves sample goals and dashboard preferences for that user in the core database.
  3. Links all six mock institutions through the core API with the tester code, exactly as
     the Connections page does, so Overview, Accounts, Plan & goals and Sam have data.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROVIDERS = ["chase", "amex", "pnc", "discover", "loans", "mortgages"]
GOALS = [
    {"name": "My undergraduate education", "kind": "education", "target_amount": "20000.00", "saved_amount": "3500.00",
     "monthly_contribution": "450.00", "months": 36, "annual_return_pct": "2.00"},
    {"name": "My next car", "kind": "car", "target_amount": "12000.00", "saved_amount": "2500.00",
     "monthly_contribution": "400.00", "months": 24, "annual_return_pct": "0"},
    {"name": "Healthier credit habits", "kind": "credit", "target_amount": "0", "saved_amount": "0",
     "monthly_contribution": "0", "months": 8, "annual_return_pct": "0", "target_score": 760, "target_utilization_pct": 25},
    {"name": "My retirement", "kind": "retirement", "target_amount": "500000.00", "saved_amount": "18000.00",
     "monthly_contribution": "600.00", "months": 360, "annual_return_pct": "6.00"},
    {"name": "My emergency cushion", "kind": "emergency", "target_amount": "10000.00", "saved_amount": "4000.00",
     "monthly_contribution": "300.00", "months": 18, "annual_return_pct": "0"},
]
PREFERENCES = {"ai_enabled": True, "show_forecast": True, "show_subscriptions": True, "show_spending": True,
               "monthly_income": None, "monthly_budget": "3200.00", "forecast_months": 12,
               "stocks_pct": 60, "bonds_pct": 25, "cash_pct": 15}


def tester_settings():
    # Environment first (Docker passes .env.tester as env vars), then the local file.
    values = {key: os.environ[key] for key in ("TESTER_EMAIL", "TESTER_CODE") if os.environ.get(key)}
    path = ROOT / ".env.tester"
    if len(values) < 2 and path.is_file():
        values = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                      if "=" in line and not line.lstrip().startswith("#"))
    elif len(values) < 2:
        sys.exit("Create .env.tester with TESTER_EMAIL and TESTER_CODE first.")
    email, code = values.get("TESTER_EMAIL", "").strip().lower(), values.get("TESTER_CODE", "").strip()
    if not email or not (len(code) == 6 and code.isdigit()):
        sys.exit(".env.tester needs TESTER_EMAIL and a six-digit TESTER_CODE.")
    return email, code


def call(api, method, path, body=None, token=None, ok=(200, 201, 202, 204)):
    request = urllib.request.Request(api.rstrip("/") + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        if error.code in ok:
            return error.code, None
        raise SystemExit(f"{method} {path} failed with HTTP {error.code}: {detail}") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000", help="core API base URL")
    args = parser.parse_args()
    email, code = tester_settings()

    print(f"1/3 Synthetic institution data for {email}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "add_demo_customer.py"), "--email", email], check=True)

    print("2/3 Signing in with the tester code")
    call(args.api, "POST", "/v1/auth/request-email-code", {"email": email})
    _, signed_in = call(args.api, "POST", "/v1/auth/verify-email-code", {"email": email, "code": code})
    token = signed_in["access_token"]

    print("    Goals and dashboard preferences")
    call(args.api, "PUT", "/v1/planning/preferences", PREFERENCES, token)
    _, existing = call(args.api, "GET", "/v1/planning/goals", token=token)
    have = {goal["name"] for goal in existing}
    for goal in GOALS:
        if goal["name"] not in have:
            body = {"target_score": None, "target_utilization_pct": 30, "show_on_dashboard": True, **goal}
            call(args.api, "POST", "/v1/planning/goals", body, token)
            print(f"    + {goal['name']}")

    print("3/3 Linking mock institutions with the tester code")
    for provider in PROVIDERS:
        status, _ = call(args.api, "POST", f"/v1/connections/{provider}/request-code", {"email": email}, token, ok=(202, 429))
        if status == 429:
            print(f"    {provider}: code requested recently; wait 30 seconds and rerun")
            continue
        _, linked = call(args.api, "POST", f"/v1/connections/{provider}/verify-code", {"email": email, "code": code}, token)
        print(f"    {provider}: linked until {linked['expires_at']}")

    call(args.api, "GET", "/v1/credit-score", token=token, ok=(200, 404, 409))
    print(f"\nDone. Sign in as {email} with the tester code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
