"""Upgrade and reconcile current synthetic credit profiles in the active local databases.

Historical application scores remain unchanged. No external bank or bureau is contacted.
"""
from datetime import date
import importlib
from pathlib import Path
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    scores = {}
    targets = [(name, "mock_bank") for name in ("chase", "amex", "pnc", "discover")]
    targets += [("loans", "mock_loan"), ("mortgages", "mock_mortgage")]
    for provider, service in targets:
        path = ROOT / "services" / service / "data" / f"{provider}.db"
        if not path.is_file():
            raise SystemExit(f"Missing active database: {provider}; initialize the services first")
        prefix = f"services.{service}.app"
        database = importlib.import_module(prefix + ".database")
        models = importlib.import_module(prefix + ".models")
        credit = importlib.import_module(prefix + ".credit")
        engine, factory = database.make_database(f"sqlite:///{path.as_posix()}")
        try:
            credit.upgrade_credit_schema(engine)
            with factory() as session:
                customers = session.scalars(select(models.Customer)).all()
                for customer in customers:
                    email = customer.email.strip().lower()
                    if email in scores and scores[email] != customer.credit_score:
                        raise RuntimeError("Conflicting current credit scores across services")
                    scores[email] = customer.credit_score
                print(f"{provider}: {len(customers)} current profiles reconciled")
        finally:
            engine.dispose()

    from backend.app.config import Settings
    from backend.app.database import Base, make_database
    from backend.app.models import Connection, CreditProfile
    engine, factory = make_database(Settings().database_url)
    try:
        Base.metadata.create_all(engine)
        with factory() as session:
            links = session.scalars(select(Connection).where(Connection.kind.in_(["mock_bank", "mock_loan", "mock_mortgage"]))).all()
            bank_scores = {}
            for link in links:
                customer = dict(link.customer_profile or {})
                score = scores.get(customer.get("email", "").strip().lower())
                if score is None:
                    continue
                customer.update(credit_score=score, credit_score_as_of=date.today().isoformat())
                link.customer_profile = customer
                if link.kind == "mock_bank":
                    bank_scores.setdefault(link.user_id, set()).add(score)
            for user_id, values in bank_scores.items():
                if len(values) != 1:
                    continue
                profile = session.get(CreditProfile, user_id)
                if profile is None:
                    profile = CreditProfile(user_id=user_id, score=values.pop(), model="Synthetic demo score v1", as_of=date.today())
                    session.add(profile)
                else:
                    profile.score, profile.as_of = values.pop(), date.today()
            session.commit()
            print(f"core: one current profile per consistent linked user ({len(bank_scores)} users checked)")
    finally:
        engine.dispose()
    print("Current scores are consistent by normalized email across all active local databases. Historical applications preserved.")


if __name__ == "__main__":
    main()
