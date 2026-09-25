"""
Apply database migrations (Alembic) — used at startup when AUTO_MIGRATE is on,
and by `python -m database.migrate`. In production run `alembic upgrade head`
once per deploy instead.

Databases created before migrations existed (tables made by the old
create_all() at startup, e.g. an existing bolobank.db) have no
`alembic_version` table. For those, any missing tables are created and the
database is recorded as up to date ("stamped"), instead of re-running the
initial migration over tables that already exist.
"""
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from database import models  # noqa: F401  (registers every table)
from database.session import Base, engine as default_engine

logger = logging.getLogger("bolobank.migrate")
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


@contextmanager
def _one_process_at_a_time(engine):
    """Several server processes may start together. Only one may migrate at
    a time, or one sees another's half-created tables. PostgreSQL: an
    advisory lock. SQLite file: an OS lock on a file next to the database."""
    if engine.dialect.name == "postgresql":
        with engine.connect() as c:
            c.execute(text("SELECT pg_advisory_lock(7263540)"))
            try:
                yield
            finally:
                c.execute(text("SELECT pg_advisory_unlock(7263540)"))
        return
    db_file = engine.url.database
    if engine.dialect.name != "sqlite" or not db_file or db_file == ":memory:":
        yield
        return
    with open(f"{db_file}.migrate.lock", "a+b") as f:
        _lock_file(f)
        try:
            yield
        finally:
            _unlock_file(f)


def _lock_file(f, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if os.name == "nt":
                import msvcrt

                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


def _unlock_file(f) -> None:
    if os.name == "nt":
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def migrate(engine=None) -> str:
    """Returns what was done: "upgraded" or "stamped-existing-database"."""
    engine = engine or default_engine
    with _one_process_at_a_time(engine):
        return _migrate(engine)


def _migrate(engine) -> str:
    cfg = _config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and tables & {"staff", "turns"}:
            Base.metadata.create_all(connection)  # only adds missing tables; never changes existing ones
            command.stamp(cfg, "head")
            logger.info("Existing database recorded at the latest migration")
            return "stamped-existing-database"
        command.upgrade(cfg, "head")
        return "upgraded"


def migrate_at_startup(engine=None, attempts: int = 5) -> str:
    """For AUTO_MIGRATE. When several server processes start together
    (uvicorn --workers N) they all try to migrate at the same moment; the
    losers hit "table already exists" or a locked database. Waiting and
    re-checking lets them see the finished result instead of crashing."""
    for attempt in range(1, attempts + 1):
        try:
            return migrate(engine)
        except Exception as exc:
            if attempt == attempts:
                raise
            logger.info("Database migration busy (%s); retrying", type(exc).__name__)
            time.sleep(0.5 * attempt)
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    print(migrate())
