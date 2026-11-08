"""Persistent, deterministic synthetic borrowers and loan records."""
from datetime import datetime, time, timezone, date
import secrets
from faker import Faker
from sqlalchemy import select
from .config import Settings
from .models import Customer, Metadata
from .schemas import ApplicationIn
from .loan_service import build_application

def seed_loans(session, settings: Settings) -> None:
    existing = session.get(Metadata, "platform")
    lender = session.get(Metadata, "lender_id")
    if existing:
        if existing.value != "mock_loans" or lender is None or lender.value != settings.lender_id:
            raise ValueError("Database belongs to another platform or institution")
        return
    if lender or session.scalar(select(Customer.id).limit(1)):
        raise ValueError("Choose a separate database file for the mock loan platform")
    session.add_all([Metadata(key="platform", value="mock_loans"), Metadata(key="lender_id", value=settings.lender_id),
                     Metadata(key="signing_secret", value=secrets.token_urlsafe(48))])
    fake = Faker("en_US")
    fake.seed_instance(settings.data_seed)
    stamp = datetime.combine(settings.seed_date, time(), timezone.utc)
    for number in range(1, 6):
        cid = f"{settings.lender_id}-customer-{number:03}"
        session.add(Customer(id=cid, first_name=fake.first_name(), last_name=fake.last_name(),
            email=f"customer{number}@{settings.lender_id}.example.test", date_of_birth=date(1980+number, 3, 12),
            synthetic_identity_id=f"SYNTH-{cid}", created_at=stamp))
        session.flush()
        for kind, amount, term in [("personal_loan", "10000.00", 36), ("auto_loan", "25000.00", 60)]:
            body = ApplicationIn(loan_type=kind, amount=amount, term_months=term, annual_income="90000.00",
                                 existing_monthly_debt="300.00", credit_score=680+number*10)
            session.add(build_application(body, cid, f"{cid}-{kind}", stamp))
    session.commit()



def main() -> None:
    from .database import Base, make_database
    settings = Settings()
    engine, factory = make_database(settings.database_url)
    try:
        Base.metadata.create_all(engine)
        with factory() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            seed_loans(session, settings)
        print(f"Loan data ready; demo email: customer1@{settings.lender_id}.example.test")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
