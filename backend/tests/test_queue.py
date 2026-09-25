"""Branch queue stored in the database (services/queue_service.py)."""
from auth.security import create_access_token
from database.models import QueueToken
from database.session import SessionLocal

STAFF = {"Authorization": f"Bearer {create_access_token('staff')}"}


def _clear():
    db = SessionLocal()
    db.query(QueueToken).delete()
    db.commit()
    db.close()


def test_elderly_customers_are_called_first_and_state_is_shared(client):
    _clear()
    add = lambda name, kind: client.post("/api/queue/token", headers=STAFF, json={"customer_name": name, "service_type": "deposit", "customer_type": kind}).json()  # noqa: E731
    a = add("Vijay", "general")
    b = add("Meena", "elderly")
    c = add("Shankar", "general")
    assert [a["token"], b["token"], c["token"]] == ["T001", "T002", "T003"]

    state = client.get("/api/queue", headers=STAFF).json()
    assert [t["customer_name"] for t in state["waiting"]] == ["Meena", "Vijay", "Shankar"]

    assert client.post("/api/queue/call-next", headers=STAFF).json()["customer_name"] == "Meena"
    assert client.post("/api/queue/call-next", headers=STAFF).json()["customer_name"] == "Vijay"
    state = client.get("/api/queue", headers=STAFF).json()
    assert [t["customer_name"] for t in state["serving"]] == ["Vijay"]
    assert [t["customer_name"] for t in state["done"]] == ["Meena"]
    assert [t["customer_name"] for t in state["waiting"]] == ["Shankar"]


def test_queue_survives_a_restart(client):
    """The queue lives in the database, so a new service instance (like a
    restarted server process) sees the same tokens."""
    _clear()
    client.post("/api/queue/token", headers=STAFF, json={"customer_name": "Ramesh", "service_type": "pension", "customer_type": "elderly"})
    from services.queue_service import QueueService

    db = SessionLocal()
    fresh = QueueService().get_state(db)
    db.close()
    assert [t["customer_name"] for t in fresh["waiting"]] == ["Ramesh"]


def test_empty_queue(client):
    _clear()
    assert client.post("/api/queue/call-next", headers=STAFF).json() == {"message": "Queue is empty"}
