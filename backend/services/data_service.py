import json
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _load_json(filename: str) -> Any:
    with (DATA_DIR / filename).open("r", encoding="utf-8") as f:
        return json.load(f)


CUSTOMERS: List[Dict[str, Any]] = _load_json("customers.json")
TRANSACTIONS: List[Dict[str, Any]] = _load_json("transactions.json")
DEMO_QUEUE: List[Dict[str, Any]] = _load_json("queue.json")
DEMO_SESSIONS: List[Dict[str, Any]] = _load_json("sessions.json")


def get_customers() -> List[Dict[str, Any]]:
    return CUSTOMERS


def get_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    return next((c for c in CUSTOMERS if c.get("customer_id") == customer_id), None)


def get_customer_transactions(customer_id: str) -> List[Dict[str, Any]]:
    return [t for t in TRANSACTIONS if t.get("customer_id") == customer_id]


def get_demo_queue() -> List[Dict[str, Any]]:
    return DEMO_QUEUE


def get_demo_sessions() -> List[Dict[str, Any]]:
    return DEMO_SESSIONS
