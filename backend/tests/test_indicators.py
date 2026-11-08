from decimal import Decimal

from app.domain.models import Account, AccountType, FinancialProfile
from app.engine import indicators as ind
from app.engine.indicators import Status


def card(id_: str, balance: str, limit: str | None, apr: str = "0.20") -> Account:
    return Account(
        id=id_,
        institution="Test",
        type=AccountType.CREDIT_CARD,
        nickname=id_,
        balance=Decimal(balance),
        annual_rate=Decimal(apr),
        credit_limit=Decimal(limit) if limit else None,
    )


def by_key(report: ind.HealthReport) -> dict[str, ind.Indicator]:
    return {i.key: i for i in report.indicators}


def test_alex_report_matches_whiteboard_numbers(alex):
    report = by_key(ind.health_report(alex))

    # $600 / $2,500 = 24% -> under 30% but over 10%
    assert report["credit_utilization"].value == Decimal("0.2400")
    assert report["credit_utilization"].status is Status.FAIR

    # ($5,000 + $1,700) / $1,500 = 4.47 months
    assert report["emergency_fund_months"].value == Decimal("4.4667")
    assert report["emergency_fund_months"].status is Status.FAIR

    # ($3,200 - $1,500) / $3,200
    assert report["savings_rate"].value == Decimal("0.5313")
    assert report["savings_rate"].status is Status.GOOD

    # Spare cash above 3-month buffer = 6,700 - 4,500 = 2,200 >= $600 debt.
    # Paying it saves (18% - 5%) * 600 = $78/year.
    assert report["debt_payoff_savings"].value == Decimal("78.00")
    assert report["debt_payoff_savings"].status is Status.FAIR


def test_utilization_aggregates_cards_and_skips_unknown_limits():
    accounts = (card("a", "100", "1000"), card("b", "400", "1000"), card("c", "999", None))
    assert ind.credit_utilization(accounts) == Decimal("0.2500")


def test_utilization_unknown_when_no_limits():
    assert ind.credit_utilization((card("c", "500", None),)) is None


def test_missing_expenses_gives_unknown_not_a_guess(alex):
    profile = alex.model_copy(update={"monthly_expenses": None})
    report = by_key(ind.health_report(profile))
    for key in ("emergency_fund_months", "savings_rate", "debt_payoff_savings"):
        assert report[key].value is None
        assert report[key].status is Status.UNKNOWN


def test_payoff_never_touches_emergency_buffer():
    profile = FinancialProfile(
        customer_id="x",
        display_name="X",
        monthly_expenses=Decimal("1000"),
        accounts=(
            card("cc", "5000", "10000", apr="0.25"),
            Account(
                id="sav",
                institution="T",
                type=AccountType.SAVINGS,
                nickname="s",
                balance=Decimal("3500"),
                annual_rate=Decimal("0.05"),
            ),
        ),
    )
    # Only $500 is above the $3,000 buffer: 500 * (0.25 - 0.05) = 100
    assert ind.debt_payoff_savings(profile) == Decimal("100.00")


def test_payoff_targets_highest_apr_first():
    profile = FinancialProfile(
        customer_id="x",
        display_name="X",
        monthly_expenses=Decimal("0"),
        accounts=(
            card("low", "1000", "5000", apr="0.10"),
            card("high", "1000", "5000", apr="0.30"),
            Account(
                id="chk",
                institution="T",
                type=AccountType.CHECKING,
                nickname="c",
                balance=Decimal("1000"),
            ),
        ),
    )
    # $1,000 spare goes to the 30% card: 1000 * 0.30
    assert ind.debt_payoff_savings(profile) == Decimal("300.00")
