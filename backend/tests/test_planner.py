from decimal import Decimal

import pytest

from app.domain.errors import InvalidRequestError, NotFoundError
from app.engine import planner


def test_required_payment_reaches_target_and_is_minimal():
    balance, target, apr, months = Decimal("600"), Decimal("250"), Decimal("0.18"), 6
    payment = planner.required_monthly_payment(balance, target, apr, months)

    balances, *_ = planner.simulate(balance, apr, payment, months)
    assert balances[-1] <= target

    one_cent_less, *_ = planner.simulate(balance, apr, payment - Decimal("0.01"), months)
    assert one_cent_less[-1] > target  # proves we didn't overshoot


def test_zero_interest_is_simple_division():
    assert planner.required_monthly_payment(
        Decimal("600"), Decimal("250"), Decimal("0"), 7
    ) == Decimal("50.00")


def test_already_at_target_needs_no_payment():
    assert planner.required_monthly_payment(
        Decimal("100"), Decimal("250"), Decimal("0.18"), 6
    ) == Decimal("0")


def test_alex_utilization_plan(alex):
    plan = planner.plan_utilization_goal(alex, "pnc-cc-1", Decimal("0.10"), months=6)
    assert plan.current_utilization == Decimal("0.2400")
    assert plan.target_balance == Decimal("250.00")
    assert plan.monthly_payment == Decimal("65.19")
    assert plan.projection.balances[-1] <= plan.target_balance
    assert plan.projection.total_interest > 0


def test_projection_pays_off_without_going_negative(alex):
    proj = planner.project(alex, "pnc-cc-1", Decimal("200"), months=6)
    assert proj.paid_off_in_month == 4
    assert all(b >= 0 for b in proj.balances)
    assert proj.balances[-1] == 0
    assert proj.total_paid == Decimal("600") + proj.total_interest


@pytest.mark.parametrize(
    ("account_id", "target", "months", "error"),
    [
        ("c1-chk-1", "0.10", 6, InvalidRequestError),  # checking is not debt
        ("pnc-cc-1", "1.00", 6, InvalidRequestError),  # 100% is not a goal
        ("pnc-cc-1", "-0.1", 6, InvalidRequestError),
        ("pnc-cc-1", "0.10", 0, InvalidRequestError),
        ("pnc-cc-1", "0.10", 361, InvalidRequestError),
        ("nope", "0.10", 6, NotFoundError),
    ],
)
def test_plan_rejects_bad_input(alex, account_id, target, months, error):
    with pytest.raises(error):
        planner.plan_utilization_goal(alex, account_id, Decimal(target), months)
