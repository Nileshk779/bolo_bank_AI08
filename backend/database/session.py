"""
Database engine and sessions.

DATABASE_URL selects the database:
  * not set (default)            -> SQLite file (DATABASE_PATH / backend/bolobank.db),
                                    for local development and demos
  * postgresql+psycopg://...     -> PostgreSQL, for production: many server
                                    processes can write at the same time
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import settings

DATABASE_URL = settings.DATABASE_URL
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        """Requests run in parallel threads. WAL lets readers work while one
        request writes, and busy_timeout makes a writer wait for the lock
        rather than fail."""
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
else:
    # A pool per server process. pool_size + max_overflow should cover
    # WORKER_THREADS; pre_ping drops connections the database has closed.
    engine = create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
