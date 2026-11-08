"""Shared synthetic-credit-v1 policy, vendored so each service deploys independently.

This is fictional profile data, never a bureau score or an underwriting decision.
The same normalized email yields the same current score on every mock server.
"""
from datetime import date
from sqlalchemy import inspect, text

CREDIT_MODEL = "Synthetic demo score v1"

def synthetic_credit_score(email: str) -> int:
    value = 2166136261
    for byte in email.strip().lower().encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return 650 + value % 151

def customer_score_default(context):
    return synthetic_credit_score(context.get_current_parameters()["email"])

def upgrade_credit_schema(engine):
    """Add and backfill profile fields; leave historical application inputs alone."""
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("customers")}
        if "credit_score" not in columns:
            connection.execute(text("ALTER TABLE customers ADD COLUMN credit_score INTEGER NULL"))
        if "credit_score_as_of" not in columns:
            connection.execute(text("ALTER TABLE customers ADD COLUMN credit_score_as_of DATE NULL"))
        rows = connection.execute(text("SELECT id, email, credit_score, credit_score_as_of FROM customers")).mappings().all()
        for row in rows:
            score = synthetic_credit_score(row["email"])
            if row["credit_score"] != score or row["credit_score_as_of"] is None:
                connection.execute(text("UPDATE customers SET credit_score=:score, credit_score_as_of=:as_of WHERE id=:id"),
                    {"score":score, "as_of":date.today(), "id":row["id"]})
