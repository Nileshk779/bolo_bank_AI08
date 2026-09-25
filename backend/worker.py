"""
Background worker — runs scheduled jobs outside the web servers.

    python worker.py

In production run one (or more — the database lock makes sure each job runs
once per interval) worker process, and set SCHEME_AUTO_UPDATE=false on the
API servers so they only serve requests. Jobs:
  * daily scheme update (services/scheme_update_service.py)
"""
import logging
import signal
import time

from core.config import settings
from core.logging import setup_logging
from services.scheme_update_service import run_scheduled_update

setup_logging()
logger = logging.getLogger("bolobank.worker")
_stop = False


def _handle_stop(*_):
    global _stop
    _stop = True
    logger.info("Worker stopping")


def main() -> None:
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    logger.info("Worker started: scheme update every %s h", settings.SCHEME_UPDATE_INTERVAL_HOURS)
    while not _stop:
        try:
            run_scheduled_update()
        except Exception:
            logger.exception("Scheduled scheme update failed")
        # Sleep in short steps so a stop signal is handled promptly.
        deadline = time.monotonic() + settings.SCHEME_UPDATE_INTERVAL_HOURS * 3600
        while not _stop and time.monotonic() < deadline:
            time.sleep(min(5.0, deadline - time.monotonic()))


if __name__ == "__main__":
    main()
