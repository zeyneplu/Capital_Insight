from decimal import Decimal
import logging
import re
import pytest
from fastapi.testclient import TestClient
from services.mock_loan.app.main import create_app
from services.mock_loan.app.config import Settings
from services.mock_loan.app.schemas import ApplicationIn
from services.mock_loan.app.loan_service import build_application, schedule_for, payment_for


def body(**overrides):
    return {"loan_type": "personal_loan", "amount": "10000.00", "term_months": 36,
            "annual_income": "72000.00", "existing_monthly_debt": "300.00", "credit_score": 720, **overrides}


def test_loan_only_api(loan_client):
    assert loan_client.get("/health").json()["lender_id"] == "loans"
    assert len(loan_client.get("/v1/loan-offers").json()) == 3
    assert loan_client.get("/v1/loans").status_code == 401
    paths = loan_client.get("/openapi.json").json()["paths"]
    assert "/v1/accounts" not in paths
    assert "/v1/loan-applications" in paths
    assert loan_client.get("/docs").status_code == 200


def test_apply_approved_and_declined(loan_client, loan_headers):
    response = loan_client.post("/v1/loan-applications", json=body(), headers=loan_headers)
    assert response.status_code == 201
    approved = response.json()
    assert approved["status"] == "approved"
    assert isinstance(approved["monthly_payment"], str)
    assert Decimal(approved["monthly_payment"]) == Decimal("322.20")
    assert loan_client.get(f"/v1/loan-applications/{approved['id']}", headers=loan_headers).json()["id"] == approved["id"]
    for overrides in ({"credit_score": 500}, {"annual_income": "12000.00", "existing_monthly_debt": "800.00"}):
        response = loan_client.post("/v1/loan-applications", json=body(**overrides), headers=loan_headers)
        assert response.status_code == 201
        declined = response.json()
        assert declined["status"] == "declined"
        assert loan_client.get(f"/v1/loans/{declined['id']}/schedule", headers=loan_headers).status_code == 409
    assert len(loan_client.get("/v1/loan-applications", headers=loan_headers).json()) == 5
    assert len(loan_client.get("/v1/loans", headers=loan_headers).json()) == 3


def test_schedule_and_ownership(loan_client, loan_headers):
    loans = loan_client.get("/v1/loans", headers=loan_headers).json()
    assert len(loans) == 2
    for loan in loans:
        result = loan_client.get(f"/v1/loans/{loan['id']}/schedule", headers=loan_headers)
        assert result.status_code == 200
        schedule = result.json()
        assert len(schedule) == loan["term_months"]
        assert sum(Decimal(row["principal"]) for row in schedule) == Decimal(loan["amount"])
        assert Decimal(schedule[-1]["remaining_balance"]) == 0
        assert all(Decimal(row["payment"]) == Decimal(row["principal"])+Decimal(row["interest"]) for row in schedule)
    for path in ("/v1/loan-applications/loans-customer-002-personal_loan", "/v1/loans/loans-customer-002-personal_loan/schedule"):
        assert loan_client.get(path, headers=loan_headers).status_code == 404


@pytest.mark.parametrize("overrides", [{"amount": "0"}, {"amount": "999.00"}, {"term_months": 13}, {"credit_score": 900},
                                       {"annual_income": "0"}, {"existing_monthly_debt": "-1"}, {"amount": "NaN"}, {"amount": "1000.001"}])
def test_validation(loan_client, loan_headers, overrides):
    assert loan_client.post("/v1/loan-applications", json=body(**overrides), headers=loan_headers).status_code == 422


def test_loan_persistence(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'persistent.db'}")
    snapshots = []
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            with client.app.state.session_factory() as session:
                from sqlalchemy import select
                from services.mock_loan.app.models import LoanApplication
                snapshots.append([(a.id, a.amount, a.created_at) for a in session.scalars(select(LoanApplication).order_by(LoanApplication.id))])
    assert snapshots[0] == snapshots[1]
    assert len(snapshots[0]) == 10


def test_calendar_and_zero_interest():
    from datetime import datetime, timezone
    assert payment_for(Decimal("1200"), Decimal("0"), 12) == Decimal("100.00")
    application = build_application(ApplicationIn(**body()), "demo", created_at=datetime(2026, 1, 31, tzinfo=timezone.utc))
    schedule = schedule_for(application)
    assert schedule[0].due_date.isoformat() == "2026-02-28"
    assert schedule[1].due_date.isoformat() == "2026-03-31"
