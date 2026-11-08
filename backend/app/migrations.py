"""Additive v2 upgrade: preserve existing users, connections and cached data."""
from sqlalchemy import inspect, text


def upgrade_schema(engine):
    with engine.begin() as connection:
        inspector = inspect(connection)
        users = {column["name"] for column in inspector.get_columns("users")}
        links = {column["name"] for column in inspector.get_columns("connections")}
        if "email_verified_at" not in users:
            timestamp = "TIMESTAMP WITH TIME ZONE" if connection.dialect.name == "postgresql" else "TIMESTAMP"
            connection.execute(text(f"ALTER TABLE users ADD COLUMN email_verified_at {timestamp} NULL"))
        if "customer_profile" not in links:
            connection.execute(text("ALTER TABLE connections ADD COLUMN customer_profile JSON NULL"))
