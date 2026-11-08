"""NessieSource against a fake Nessie server that returns documented Nessie shapes,
including messy records (cancelled, missing dates, declined loans, unknown merchants)."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.domain.errors import NotFoundError
from app.domain.models import AccountType
from app.sources.nessie import NessieError, NessieSource

KEY = "test-key-123"

ROUTES: dict[str, object] = {
    "/customers": [{"_id": "c1", "first_name": "Sam", "last_name": "Lee"}],
    "/customers/c1": {"_id": "c1", "first_name": "Sam", "last_name": "Lee"},
    "/customers/c1/accounts": [
        {"_id": "chk", "type": "Checking", "nickname": "Main", "balance": 1200.5},
        {"_id": "cc", "type": "Credit Card", "nickname": "", "balance": -300},
        {"_id": "biz", "type": "Business", "balance": 99},  # unmodeled -> skipped
    ],
    "/accounts/chk/loans": [
        {"_id": "L1", "type": "home", "status": "approved", "credit_score": 712,
         "monthly_payment": 1850, "amount": 284000, "description": "Home loan"},
        {"_id": "L2", "type": "auto", "status": "declined", "credit_score": 712,
         "monthly_payment": 300, "amount": 9000},
    ],
    "/accounts/chk/deposits": [
        {"_id": "d1", "medium": "balance", "transaction_date": "2026-10-01",
         "status": "completed", "amount": 1600, "description": "Payroll"},
        {"_id": "d2", "medium": "balance", "transaction_date": "2026-10-15",
         "status": "completed", "amount": 1600, "description": "Payroll"},
    ],
    "/accounts/chk/withdrawals": [
        {"_id": "w1", "medium": "balance", "transaction_date": "2026-10-03",
         "status": "completed", "amount": 60, "description": "ATM"},
    ],
    "/accounts/cc/purchases": [
        {"_id": "p1", "merchant_id": "m-food", "medium": "balance",
         "purchase_date": "2026-10-10", "amount": 42.5, "status": "completed",
         "description": "Lunch"},
        {"_id": "p2", "merchant_id": "m-gone", "medium": "balance",
         "purchase_date": "2026-10-11", "amount": 20, "status": "completed"},
        {"_id": "p3", "merchant_id": "m-food", "purchase_date": "2026-10-12",
         "amount": 999, "status": "cancelled"},  # cancelled -> skipped
        {"_id": "p4", "merchant_id": "m-food", "amount": 5},  # no date -> skipped
    ],
    "/accounts/chk/bills": [
        {"_id": "b1", "status": "recurring", "payee": "City Power", "nickname": "Power",
         "payment_date": "2026-10-08", "recurring_date": 8,
         "upcoming_payment_date": "2026-11-08", "payment_amount": 120},
        {"_id": "b2", "status": "cancelled", "payee": "Old Gym", "payment_amount": 30},
    ],
    "/merchants/m-food": {"_id": "m-food", "name": "Taco Stand", "category": ["Food"]},
}  # fmt: skip


def fake_nessie(request: httpx.Request) -> httpx.Response:
    assert request.method == "GET"  # read-only: we never write to Nessie
    assert request.url.params["key"] == KEY
    body = ROUTES.get(request.url.path)
    if body is None:
        # Unknown sub-collections are 404s in our fake; the source treats them as empty.
        return httpx.Response(404, json={"message": "not found"})
    return httpx.Response(200, json=body)


def make_source(handler=fake_nessie) -> NessieSource:
    transport = httpx.MockTransport(handler)
    return NessieSource(httpx.AsyncClient(base_url="https://nessie.test", transport=transport), KEY)


async def test_profile_merges_accounts_loans_and_cash_flow():
    profile = await make_source().get_profile("c1")

    assert profile.display_name == "Sam Lee"
    by_id = {a.id: a for a in profile.accounts}
    assert set(by_id) == {"chk", "cc", "L1"}  # Business skipped, declined loan skipped
    assert by_id["cc"].type is AccountType.CREDIT_CARD
    assert by_id["cc"].balance == Decimal("300")  # debt stored as positive
    assert by_id["cc"].credit_limit is None  # Nessie has no limits: don't invent one
    assert by_id["L1"].type is AccountType.MORTGAGE
    assert profile.credit_score == 712  # sandbox value from loans
    # Window is anchored to the latest transaction, so old sandbox data still works.
    # Two-week sample, so averaged over 1 month (not the default 3).
    assert profile.monthly_income == Decimal("3200.00")


async def test_transactions_are_signed_categorized_and_cleaned():
    txns = await make_source().get_transactions("c1")

    assert [t.id for t in txns] == ["d2", "p2", "p1", "w1", "d1"]  # newest first
    by_id = {t.id: t for t in txns}
    assert by_id["p1"].amount == Decimal("-42.5")
    assert by_id["p1"].category == "food"  # from the merchant
    assert by_id["p2"].category == "shopping"  # merchant lookup 404 -> safe default
    assert by_id["w1"].amount == Decimal("-60") and by_id["w1"].category == "cash"
    assert by_id["d1"].amount == Decimal("1600") and by_id["d1"].category == "income"


async def test_bills_skip_cancelled():
    bills = await make_source().get_bills("c1")
    assert [(b.payee, b.amount, b.next_due, b.recurring_day) for b in bills] == [
        ("City Power", Decimal("120"), date(2026, 11, 8), 8)
    ]


async def test_list_customers():
    assert await make_source().list_customers() == [{"id": "c1", "name": "Sam Lee"}]


async def test_unknown_customer_is_not_found():
    with pytest.raises(NotFoundError):
        await make_source().get_profile("missing")


async def test_upstream_failure_never_leaks_api_key():
    with pytest.raises(NessieError) as exc_info:
        await make_source(lambda r: httpx.Response(500)).get_profile("c1")
    assert KEY not in str(exc_info.value)


async def test_customer_id_cannot_change_the_path():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.raw_path.decode())
        return httpx.Response(404)

    with pytest.raises(NotFoundError):
        await make_source(handler).get_profile("../merchants")
    assert all("..%2Fmerchants" in p for p in seen)
