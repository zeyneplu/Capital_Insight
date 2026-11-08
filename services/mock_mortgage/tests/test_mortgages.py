from decimal import Decimal
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from services.mock_mortgage.app.main import create_app
from services.mock_mortgage.app.config import Settings
from services.mock_mortgage.app.schemas import ApplicationIn
from services.mock_mortgage.app.mortgage_service import build_application, schedule_for, payment_for


def body(**overrides):
    return {"property_value": "350000.00", "down_payment": "70000.00", "term_months": 360,
            "annual_income": "120000.00", "existing_monthly_debt": "500.00", "credit_score": 740, **overrides}


def test_mortgage_only_api(mortgage_client):
    assert mortgage_client.get("/health").json()["lender_id"] == "mortgages"
    offers = mortgage_client.get("/v1/mortgage-offers").json()
    assert len(offers) == 1 and offers[0]["mortgage_type"] == "mortgage"
    assert mortgage_client.get("/v1/lender").json()["mortgage_types"] == ["mortgage"]
    assert mortgage_client.get("/v1/mortgages").status_code == 401
    paths = mortgage_client.get("/openapi.json").json()["paths"]
    assert "/v1/accounts" not in paths and "/v1/loans" not in paths
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert mortgage_client.get(path).status_code == 200


def test_apply_approved_and_declined(mortgage_client, mortgage_headers):
    response = mortgage_client.post("/v1/mortgage-applications", json=body(), headers=mortgage_headers)
    assert response.status_code == 201
    approved = response.json()
    assert approved["status"] == "approved"
    assert approved["amount"] == "280000.00"
    assert approved["loan_to_value"] == "0.8000"
    assert approved["monthly_payment"] == "1724.01"
    assert mortgage_client.get(f"/v1/mortgages/{approved['id']}", headers=mortgage_headers).status_code == 200
    for overrides in ({"credit_score": 500}, {"annual_income": "12000.00"}, {"down_payment": "1000.00"}):
        response = mortgage_client.post("/v1/mortgage-applications", json=body(**overrides), headers=mortgage_headers)
        assert response.status_code == 201
        declined = response.json()
        assert declined["status"] == "declined"
        assert mortgage_client.get(f"/v1/mortgages/{declined['id']}/schedule", headers=mortgage_headers).status_code == 409
        assert mortgage_client.get(f"/v1/mortgages/{declined['id']}", headers=mortgage_headers).status_code == 404
    assert len(mortgage_client.get("/v1/mortgages", headers=mortgage_headers).json()) == 2


def test_schedule_and_ownership(mortgage_client, mortgage_headers):
    mortgages = mortgage_client.get("/v1/mortgages", headers=mortgage_headers).json()
    assert len(mortgages) == 1
    for mortgage in mortgages:
        result = mortgage_client.get(f"/v1/mortgages/{mortgage['id']}/schedule", headers=mortgage_headers)
        assert result.status_code == 200
        schedule = result.json()
        assert len(schedule) == mortgage["term_months"]
        assert sum(Decimal(row["principal"]) for row in schedule) == Decimal(mortgage["amount"])
        assert Decimal(schedule[-1]["remaining_balance"]) == 0
        assert all(Decimal(row["payment"]) == Decimal(row["principal"])+Decimal(row["interest"]) for row in schedule)
    for path in ("/v1/mortgage-applications/mortgages-customer-002-mortgage", "/v1/mortgages/mortgages-customer-002-mortgage", "/v1/mortgages/mortgages-customer-002-mortgage/schedule"):
        assert mortgage_client.get(path, headers=mortgage_headers).status_code == 404


@pytest.mark.parametrize("overrides", [{"property_value": "0"}, {"down_payment": "-1"}, {"down_payment": "350000.00"},
    {"term_months": 36}, {"credit_score": 900}, {"annual_income": "0"}, {"existing_monthly_debt": "-1"},
    {"property_value": "NaN"}, {"property_value": "350000.001"}, {"mortgage_type": "personal_loan"},
    {"property_value": "20000.00", "down_payment": "1000.00"}, {"unexpected": True}])
def test_validation(mortgage_client, mortgage_headers, overrides):
    assert mortgage_client.post("/v1/mortgage-applications", json=body(**overrides), headers=mortgage_headers).status_code == 422


def test_seed_reproducibility_and_persistence(tmp_path):
    from sqlalchemy import select
    from services.mock_mortgage.app.models import MortgageApplication, Customer
    snapshots = []
    for filename in ("first.db", "first.db", "second.db"):
        settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / filename}")
        with TestClient(create_app(settings)) as client:
            with client.app.state.session_factory() as session:
                snapshots.append(([(a.id, a.amount, a.created_at) for a in session.scalars(select(MortgageApplication).order_by(MortgageApplication.id))],
                                  [(c.id, c.first_name, c.last_name) for c in session.scalars(select(Customer).order_by(Customer.id))]))
                tables = session.connection().exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars().all()
                assert "accounts" not in tables and "loan_applications" not in tables
                assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert len(snapshots[0][0]) == 5


def test_calendar_and_zero_interest():
    assert payment_for(Decimal("1200"), Decimal("0"), 12) == Decimal("100.00")
    application = build_application(ApplicationIn(**body()), "demo", created_at=datetime(2026, 1, 31, tzinfo=timezone.utc))
    schedule = schedule_for(application)
    assert schedule[0].due_date.isoformat() == "2026-02-28"
    assert schedule[1].due_date.isoformat() == "2026-03-31"
