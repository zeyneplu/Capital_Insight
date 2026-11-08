"""The contract every data source implements (the "port" in ports-and-adapters).

Add a source = write one class with this method. Nothing else in the app changes.
"""

from typing import Protocol

from app.domain.models import FinancialProfile, Transaction


class FinancialDataSource(Protocol):
    async def get_profile(self, customer_id: str) -> FinancialProfile:
        """Return the normalized profile, or raise NotFoundError."""
        ...

    async def get_transactions(self, customer_id: str) -> list[Transaction]:
        """All transactions across the customer's accounts, newest first."""
        ...
