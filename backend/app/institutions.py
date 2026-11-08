"""Registry of the mock institutions this backend aggregates."""
from dataclasses import dataclass
from typing import Literal

from .config import Settings

Service = Literal["mock_bank", "mock_loan", "mock_mortgage"]


@dataclass(frozen=True)
class Institution:
    id: str
    name: str
    service: Service
    base_url: str


def build_registry(settings: Settings) -> dict[str, Institution]:
    items = [
        Institution("chase", "Chase Mock Bank", "mock_bank", settings.chase_url),
        Institution("amex", "American Express Mock Bank", "mock_bank", settings.amex_url),
        Institution("pnc", "PNC Mock Bank", "mock_bank", settings.pnc_url),
        Institution("discover", "Discover Mock Bank", "mock_bank", settings.discover_url),
        Institution("loans", "Capital Insight Mock Loans", "mock_loan", settings.loans_url),
        Institution("mortgages", "Capital Insight Mock Mortgages", "mock_mortgage", settings.mortgages_url),
    ]
    return {item.id: item for item in items}


# Path segments per lender service (see services/mock_loan and services/mock_mortgage).
LENDER_PATHS = {
    "mock_loan": {"offers": "loan-offers", "applications": "loan-applications", "records": "loans"},
    "mock_mortgage": {"offers": "mortgage-offers", "applications": "mortgage-applications", "records": "mortgages"},
}
