"""Fail background jobs whose result never arrived.

Workers report their own failures. A job whose report was lost, for example
because the API was unreachable, stays queued; this marks it failed so the UI
offers a retry.

    python -m src.management.sweep [--every SECONDS]

With --every, it runs in a loop; the deployment runs it that way.
"""

import argparse
import logging
import time
from datetime import timedelta

from src import database
from src.model_registry import import_models
from src.moments import service as moments_service
from src.videos import overview

logger = logging.getLogger("vidwiz.sweep")

# Longer than every attempt plus the waits between them: an overview job is
# received up to 3 times, 30 minutes apart; an AI line job about 3 minutes apart.
OVERVIEW_STALE_AFTER = timedelta(hours=2)
AI_LINE_STALE_AFTER = timedelta(minutes=30)


def sweep_once() -> None:
    db = database.SessionLocal()
    try:
        overviews = overview.sweep(db, OVERVIEW_STALE_AFTER)
        lines = moments_service.sweep_stale_ai(db, AI_LINE_STALE_AFTER)
        if overviews or lines:
            logger.warning(
                "Failed stale jobs: overviews=%d ai_lines=%d", overviews, lines
            )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail stale background jobs")
    parser.add_argument("--every", type=int, help="Repeat every N seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import_models()
    while True:
        sweep_once()
        if not args.every:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
