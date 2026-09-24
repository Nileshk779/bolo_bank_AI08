"""
Queue/token management.

The original main.py used a module-level `QUEUE = []` list and a
`TOKEN_COUNTER = 0` int, mutated via the `global` keyword inside route
handlers — global mutable state directly inside the API layer. This version
keeps the exact same in-memory, non-persistent behavior (the queue still
resets on restart, and still isn't safe across multiple worker processes —
that trade-off is unchanged), but encapsulates the state inside a single
QueueService instance instead of bare module globals, so the mutation is
localized to this one class rather than reachable/mutable from anywhere
that imports the module.

Moving this to a DB-backed table (so it also survives restarts and works
across multiple workers) is a reasonable next step, but is a behavior
change, not just a structural one — deliberately left out of this
architecture-only refactor.
"""
import time


class QueueService:
    def __init__(self):
        self._queue: list[dict] = []
        self._token_counter = 0

    def add_token(self, customer_name: str, service_type: str, customer_type: str) -> dict:
        self._token_counter += 1
        token = {
            "token": f"T{self._token_counter:03d}",
            "customer_name": customer_name,
            "service_type": service_type,
            "customer_type": customer_type,
            "status": "waiting",
            "created_at": time.time(),
        }
        # Elderly customers are inserted ahead of general-queue waiters (priority lane)
        if customer_type == "elderly":
            insert_at = next(
                (i for i, t in enumerate(self._queue) if t["status"] == "waiting" and t["customer_type"] != "elderly"),
                len(self._queue),
            )
            self._queue.insert(insert_at, token)
        else:
            self._queue.append(token)
        return token

    def get_state(self) -> dict:
        return {
            "waiting": [t for t in self._queue if t["status"] == "waiting"],
            "serving": [t for t in self._queue if t["status"] == "serving"],
            "done": [t for t in self._queue if t["status"] == "done"],
        }

    def call_next(self) -> dict | None:
        for t in self._queue:
            if t["status"] == "serving":
                t["status"] = "done"
        for t in self._queue:
            if t["status"] == "waiting":
                t["status"] = "serving"
                return t
        return None


# Single shared instance for the process — same effective lifetime/scope as
# the original module-level list, just no longer a bare global.
queue_service = QueueService()
