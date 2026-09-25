"""Database migrations (database/migrate.py, migrations/)."""
import tempfile

from sqlalchemy import create_engine, inspect, text

from database.migrate import migrate
from database.session import Base

EXPECTED = {"staff", "turns", "scheme_drafts", "scheme_update_runs", "scheme_alerts", "interaction_events", "job_locks", "queue_tokens"}


def _engine():
    path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    return create_engine(f"sqlite:///{path}")


def _version(engine):
    with engine.connect() as c:
        return c.execute(text("select version_num from alembic_version")).scalar()


def test_fresh_database_is_built_from_migrations():
    engine = _engine()
    assert migrate(engine) == "upgraded"
    assert EXPECTED <= set(inspect(engine).get_table_names())
    assert _version(engine) == "0001"
    assert migrate(engine) == "upgraded"  # running again is a no-op


def test_database_from_before_migrations_is_stamped_not_rebuilt():
    engine = _engine()
    # An old bolobank.db: only the original tables, created by create_all, with data.
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["staff"], Base.metadata.tables["turns"]])
    with engine.begin() as c:
        c.execute(text("insert into turns (session_id, role, language, text_local) values ('s1', 'customer', 'mr', 'hello')"))
    assert migrate(engine) == "stamped-existing-database"
    assert EXPECTED <= set(inspect(engine).get_table_names())  # missing tables added
    assert _version(engine) == "0001"
    with engine.connect() as c:
        assert c.execute(text("select count(*) from turns")).scalar() == 1  # data kept


def test_models_and_migrations_agree():
    """Fails if database/models.py changed without a new migration
    (run: alembic revision --autogenerate -m "...")."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    engine = _engine()
    migrate(engine)
    with engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diff == []


def test_processes_starting_together_all_succeed():
    """uvicorn --workers N: every process migrates at startup at the same time."""
    from concurrent.futures import ThreadPoolExecutor

    from database.migrate import migrate_at_startup

    engine = _engine()
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: migrate_at_startup(engine), range(4)))
    assert set(results) == {"upgraded"}
    assert EXPECTED <= set(inspect(engine).get_table_names())
    assert _version(engine) == "0001"
