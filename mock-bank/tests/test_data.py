from decimal import Decimal

from tests.conftest import ALEX, JORDAN, auth, connect


def test_same_code_different_bank(make_client):
    pecan = make_client(bank_id="pecan")
    comet = make_client(bank_id="comet", bank_name="Comet Card (demo)")

    assert comet.get("/v1/bank").json()["name"] == "Comet Card (demo)"
    cards = comet.get("/v1/accounts", headers=auth(connect(comet, ALEX))).json()["accounts"]
    assert [(c["type"], c["balance"], c["credit_limit"]) for c in cards] == [
        ("credit_card", "600.00", "2500.00")
    ]
    # Alex's Pecan accounts are not at Comet, and IDs never collide across banks.
    pecan_ids = {
        a["id"]
        for a in pecan.get("/v1/accounts", headers=auth(connect(pecan, ALEX))).json()["accounts"]
    }
    assert pecan_ids.isdisjoint({c["id"] for c in cards})


def test_replicas_with_same_seed_serve_identical_data(make_client):
    def snapshot(client):
        token = connect(client, JORDAN)
        accounts = client.get("/v1/accounts", headers=auth(token)).json()["accounts"]
        txns = client.get(
            f"/v1/accounts/{accounts[0]['id']}/transactions", headers=auth(token)
        ).json()["transactions"]
        return accounts, txns

    assert snapshot(make_client()) == snapshot(make_client())
    assert snapshot(make_client()) != snapshot(make_client(seed=7))


def test_transactions_look_like_a_real_checking_account(client):
    token = connect(client, ALEX)
    checking = next(
        a
        for a in client.get("/v1/accounts", headers=auth(token)).json()["accounts"]
        if a["type"] == "checking"
    )
    txns = client.get(f"/v1/accounts/{checking['id']}/transactions", headers=auth(token)).json()[
        "transactions"
    ]

    categories = {t["category"] for t in txns}
    assert {"income", "housing", "utilities", "groceries"} <= categories
    payroll = [Decimal(t["amount"]) for t in txns if t["category"] == "income"]
    assert payroll and all(p == Decimal("1600.00") for p in payroll)  # $3,200/mo, twice monthly
    assert txns == sorted(txns, key=lambda t: t["posted_on"], reverse=True)


def test_date_filters(client):
    token = connect(client, ALEX)
    account_id = client.get("/v1/accounts", headers=auth(token)).json()["accounts"][0]["id"]
    url = f"/v1/accounts/{account_id}/transactions"

    october = client.get(
        url, headers=auth(token), params={"start_date": "2026-10-01", "end_date": "2026-10-31"}
    ).json()["transactions"]
    assert october and all(t["posted_on"].startswith("2026-10") for t in october)

    backwards = client.get(
        url, headers=auth(token), params={"start_date": "2026-10-31", "end_date": "2026-10-01"}
    )
    assert backwards.status_code == 422
