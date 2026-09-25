"""
Copy the data from a SQLite database (e.g. the demo bolobank.db) into
PostgreSQL — for moving from the laptop setup to the production stack.

    python -m database.copy_sqlite_to_postgres --from backend/bolobank.db \
        --to postgresql+psycopg://bolobank:PASSWORD@localhost:5432/bolobank

The target must already have the schema (`alembic upgrade head`, which the
docker-compose "migrate" service runs) and should be empty: tables that
already contain rows are skipped rather than overwritten. Row ids are kept,
and PostgreSQL's id counters are moved past them afterwards.
"""
import argparse

from sqlalchemy import create_engine, func, select, text

from database import models  # noqa: F401  (registers every table)
from database.session import Base


def copy(source_url: str, target_url: str) -> dict[str, int]:
    src, dst = create_engine(source_url), create_engine(target_url)
    copied = {}
    with src.connect() as s, dst.begin() as d:
        for table in Base.metadata.sorted_tables:
            if not src.dialect.has_table(s, table.name):
                continue
            if d.execute(select(func.count()).select_from(table)).scalar():
                copied[table.name] = -1  # target already has rows: left untouched
                continue
            rows = [dict(r._mapping) for r in s.execute(select(table))]
            if rows:
                d.execute(table.insert(), rows)
            copied[table.name] = len(rows)
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and pk[0].autoincrement is not False and str(pk[0].type) == "INTEGER" and rows:
                d.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                               f"(SELECT MAX({pk[0].name}) FROM {table.name}))"))
    return copied


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="source", required=True, help="path to the SQLite file")
    ap.add_argument("--to", dest="target", required=True, help="PostgreSQL URL")
    args = ap.parse_args()
    for name, n in copy(f"sqlite:///{args.source}", args.target).items():
        print(f"{name:22s} {'skipped (target not empty)' if n < 0 else f'{n} rows'}")
