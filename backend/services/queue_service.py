"""
Branch queue / tokens, stored in the database (QueueToken).

Previously an in-memory list: it reset on every restart and each server
process had its own copy. Now every process shares one queue, and it
survives restarts. Only today's tokens (branch time zone) are shown.

Elderly customers get priority: "call next" serves the waiting elderly
customer who arrived first, before general-queue customers. The response
shapes are unchanged, so the Queue screen works as before.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.config import settings
from database.models import QueueToken

PRIORITY = {"elderly": 1}


def _today_start_utc(now: datetime | None = None) -> datetime:
    offset = timedelta(minutes=settings.BRANCH_UTC_OFFSET_MINUTES)
    local = (now or datetime.utcnow()) + offset
    return local.replace(hour=0, minute=0, second=0, microsecond=0) - offset


def _as_dict(t: QueueToken) -> dict:
    return {
        "token": t.token,
        "customer_name": t.customer_name,
        "service_type": t.service_type,
        "customer_type": t.customer_type,
        "status": t.status,
        "created_at": t.created_at.timestamp() if t.created_at else None,
    }


class QueueService:
    def add_token(self, db: Session, customer_name: str, service_type: str, customer_type: str) -> dict:
        t = QueueToken(customer_name=customer_name, service_type=service_type, customer_type=customer_type,
                       priority=PRIORITY.get(customer_type, 0), status="waiting")
        db.add(t)
        db.flush()  # assigns the id
        # Token number counts today's tokens, so it restarts at T001 each day.
        number = db.query(QueueToken).filter(QueueToken.created_at >= _today_start_utc(), QueueToken.id <= t.id).count()
        t.token = f"T{number:03d}"
        db.commit()
        return _as_dict(t)

    def _ordered_waiting(self, db: Session):
        return (db.query(QueueToken)
                .filter(QueueToken.status == "waiting", QueueToken.created_at >= _today_start_utc())
                .order_by(QueueToken.priority.desc(), QueueToken.created_at, QueueToken.id))

    def get_state(self, db: Session) -> dict:
        today = db.query(QueueToken).filter(QueueToken.created_at >= _today_start_utc())
        return {
            "waiting": [_as_dict(t) for t in self._ordered_waiting(db)],
            "serving": [_as_dict(t) for t in today.filter(QueueToken.status == "serving").order_by(QueueToken.called_at)],
            "done": [_as_dict(t) for t in today.filter(QueueToken.status == "done").order_by(QueueToken.called_at)],
        }

    def call_next(self, db: Session) -> dict | None:
        db.query(QueueToken).filter(QueueToken.status == "serving").update({QueueToken.status: "done"}, synchronize_session=False)
        query = self._ordered_waiting(db)
        if db.bind.dialect.name == "postgresql":
            # Two staff members pressing "call next" together get different customers.
            query = query.with_for_update(skip_locked=True)
        nxt = query.first()
        if nxt is None:
            db.commit()
            return None
        nxt.status = "serving"
        nxt.called_at = datetime.utcnow()
        db.commit()
        return _as_dict(nxt)


queue_service = QueueService()
