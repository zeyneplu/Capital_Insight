import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fakes import FakeLLM, reply

BASE = "/api/v1/customers/demo-alex"


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_profile_and_report(client):
    profile = client.get(f"{BASE}/profile")
    assert profile.status_code == 200
    assert len(profile.json()["accounts"]) == 3

    report = client.get(f"{BASE}/health-report").json()
    util = next(i for i in report["indicators"] if i["key"] == "credit_utilization")
    assert util["value"] == "0.2400"  # Decimals travel as strings: no float rounding
    assert util["status"] == "fair"


def test_utilization_plan(client):
    resp = client.post(
        f"{BASE}/plans/credit-utilization",
        json={"account_id": "pnc-cc-1", "target_utilization": "0.10", "months": 6},
    )
    assert resp.status_code == 200
    assert resp.json()["monthly_payment"] == "65.19"


def test_errors_map_to_http_codes(client):
    assert client.get("/api/v1/customers/nobody/profile").status_code == 404
    assert (
        client.post(
            f"{BASE}/projections",
            json={"account_id": "c1-chk-1", "monthly_payment": "50", "months": 3},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{BASE}/plans/credit-utilization",
            json={"account_id": "pnc-cc-1", "target_utilization": "2", "months": 6},
        ).status_code
        == 422
    )


def test_coach_without_key_is_503_not_500(client):
    resp = client.post(f"{BASE}/coach", json={"question": "hi"})
    assert resp.status_code == 503


def test_coach_with_llm(client):
    client.app.state.llm = FakeLLM([reply(content="You're doing well.")])
    resp = client.post(f"{BASE}/coach", json={"question": "How am I doing?"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "You're doing well."


def test_nessie_mode_refuses_to_start_with_empty_key():
    settings = Settings(_env_file=None, data_source="nessie", nessie_api_key="")
    with pytest.raises(RuntimeError, match="NESSIE_API_KEY"), TestClient(create_app(settings)):
        pass


def test_coach_blocks_ssn_before_the_llm_sees_it(client):
    llm = FakeLLM([reply(content="should never be called")])
    client.app.state.llm = llm
    resp = client.post(f"{BASE}/coach", json={"question": "my SSN is 123-45-6789, help"})
    assert resp.status_code == 422
    assert llm.requests == []


def test_cash_flow(client):
    body = client.get(f"{BASE}/cash-flow", params={"months": 1}).json()
    assert body["monthly_income"] == "3200.00"
    assert body["by_category"][0] == {"category": "housing", "monthly_average": "1100.00"}
    # the $450 card payment is a transfer, so it is not counted as spending
    assert body["monthly_spending"] == "1489.79"
    assert client.get("/api/v1/customers/nobody/cash-flow").status_code == 404
