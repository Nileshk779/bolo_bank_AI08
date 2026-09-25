"""
Database-backed job lock: only one server process runs a background job per
period, however many processes are started.

acquire() succeeds for exactly one caller until the lock expires. The claim
is a single conditional INSERT/UPDATE, so two processes racing for it cannot
both win (the database decides). Works on SQLite now and PostgreSQL later.
"""
import os
import socket
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import JobLock

OWNER = f"{socket.gethostname()}:{os.getpid()}"


def acquire(db: Session, name: str, ttl_seconds: float, now: datetime | None = None, owner: str = OWNER) -> bool:
    now = now or datetime.utcnow()
    until = now + timedelta(seconds=ttl_seconds)
    # Take over the lock only if it has expired (atomic conditional update).
    updated = (
        db.query(JobLock)
        .filter(JobLock.name == name, JobLock.locked_until <= now)
        .update({JobLock.locked_until: until, JobLock.owner: owner}, synchronize_session=False)
    )
    if updated:
        db.commit()
        return True
    if db.get(JobLock, name) is not None:
        db.rollback()
        return False  # someone else holds it
    try:  # first run ever: create it; the primary key stops a second creator
        db.add(JobLock(name=name, locked_until=until, owner=owner))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
