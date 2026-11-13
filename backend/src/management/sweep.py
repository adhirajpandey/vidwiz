"""Fail background jobs whose result never arrived, drop empty chats, and embed.

Workers report their own failures. A job whose report was lost, for example
because the API was unreachable, stays queued; this marks it failed so the UI
offers a retry. Conversations that never got a message are deleted once they
are old enough that no open page still uses them. Each pass also embeds a
bounded batch of passages, moments and video cards that have no embedding.

    python -m src.management.sweep [--every SECONDS]

With --every, it runs in a loop; the deployment runs it that way.
"""

import argparse
import logging
import time
from datetime import timedelta

from src import database
from src.config import settings
from src.conversations import service as conversations_service
from src.model_registry import import_models
from src.moments import service as moments_service
from src.search.embeddings import embed_pending
from src.videos import overview

logger = logging.getLogger("vidwiz.sweep")

# Longer than every attempt plus the waits between them: an overview job is
# received up to 3 times, 30 minutes apart; an AI line job about 3 minutes apart.
OVERVIEW_STALE_AFTER = timedelta(hours=2)
AI_LINE_STALE_AFTER = timedelta(minutes=30)
# Long enough that a page opened and left without a question is long closed.
EMPTY_CONVERSATION_AFTER = timedelta(days=7)
# Rows of each kind embedded per pass; the backfill handles a large backlog.
EMBED_LIMIT = 144


def sweep_once() -> None:
    db = database.SessionLocal()
    try:
        overviews = overview.sweep(db, OVERVIEW_STALE_AFTER)
        lines = moments_service.sweep_stale_ai(db, AI_LINE_STALE_AFTER)
        if overviews or lines:
            logger.warning(
                "Failed stale jobs: overviews=%d ai_lines=%d", overviews, lines
            )
        empty = conversations_service.sweep_empty(db, EMPTY_CONVERSATION_AFTER)
        if empty:
            logger.info("Deleted empty conversations: %d", empty)
        embed(db)
    finally:
        db.close()


def embed(db) -> None:
    """Embed a batch; a failure is logged and the next pass tries again."""
    if not settings.openrouter_api_key:
        return
    try:
        counts = embed_pending(db, EMBED_LIMIT)
    except Exception:
        db.rollback()
        logger.exception("Embedding pass failed")
        return
    if counts.rows:
        logger.info(
            "Embedded: chunks=%d moments=%d videos=%d tokens=%d",
            counts.chunks,
            counts.moments,
            counts.videos,
            counts.tokens,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fail stale background jobs, delete empty conversations, and embed"
        )
    )
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
