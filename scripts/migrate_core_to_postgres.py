"""Copy the core API's local SQLite data into PostgreSQL (for example AWS RDS).

    python scripts/migrate_core_to_postgres.py                  # target = DATABASE_URL in backend/.env
    python scripts/migrate_core_to_postgres.py --dry-run        # counts only, writes nothing
    python scripts/migrate_core_to_postgres.py --source backend/data/capital_insight.db

Copies users, sessions, encrypted institution connections, Plaid cache, credit profiles,
goals, preferences and Sam chat history in foreign-key order inside one transaction.
Only the core API database moves; mock institutions keep their own SQLite files.

Keep ENCRYPTION_KEY unchanged: saved connection tokens are encrypted with it and are
copied as ciphertext. The target must be empty (the script refuses to merge).
"""
import argparse
import sys
from pathlib import Path

from sqlalchemy import func, inspect, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app import models  # noqa: E402,F401  (registers every table)
from backend.app.config import Settings  # noqa: E402
from backend.app.database import Base, make_database  # noqa: E402
from backend.app.migrations import upgrade_schema  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(ROOT / "backend" / "data" / "capital_insight.db"), help="SQLite file to copy from")
    parser.add_argument("--target", help="PostgreSQL URL (default: DATABASE_URL from backend/.env)")
    parser.add_argument("--dry-run", action="store_true", help="show row counts without writing")
    args = parser.parse_args()

    settings = Settings()
    target_url = args.target or settings.database_url
    if not target_url.startswith(("postgresql", "postgres://")):
        print("Target must be PostgreSQL. Set DATABASE_URL in backend/.env or pass --target.")
        return 1
    source_path = Path(args.source).resolve()
    if not source_path.exists():
        print(f"Source SQLite database not found: {source_path}")
        return 1

    source, _ = make_database(f"sqlite:///{source_path.as_posix()}")
    target, _ = make_database(target_url, sslmode=settings.database_sslmode, sslrootcert=settings.database_sslrootcert,
                              connect_timeout=settings.database_connect_timeout_seconds)
    print(f"Source: {source_path}\nTarget: {target.url.render_as_string(hide_password=True)}")

    present = set(inspect(source).get_table_names())
    tables = [table for table in Base.metadata.sorted_tables if table.name in present]
    with source.connect() as reader:
        counts = {table.name: reader.scalar(select(func.count()).select_from(table)) for table in tables}
    for name, count in counts.items():
        print(f"  {name:<22} {count:>7} rows")
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0

    Base.metadata.create_all(target)
    upgrade_schema(target)
    with target.connect() as checker:
        occupied = [table.name for table in tables if checker.scalar(select(func.count()).select_from(table))]
    if occupied:
        print(f"Target already has data in: {', '.join(occupied)}. Refusing to merge; use an empty database.")
        return 1

    # Older SQLite files may lack newer columns; copy only columns present on both sides.
    with source.connect() as reader, target.begin() as writer:
        for table in tables:
            columns = [column for column in table.columns if column.name in {c["name"] for c in inspect(source).get_columns(table.name)}]
            rows = [dict(row._mapping) for row in reader.execute(select(*columns))]
            for start in range(0, len(rows), 500):
                writer.execute(table.insert(), rows[start:start + 500])
    with target.connect() as checker:
        for table in tables:
            copied = checker.scalar(select(func.count()).select_from(table))
            if copied != counts[table.name]:
                print(f"Row count mismatch in {table.name}: {copied} != {counts[table.name]}")
                return 1
    print("Done. Every table matches. Keep the SQLite file as a backup until you have verified the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
