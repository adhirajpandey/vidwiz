"""One-time data backfills for v3.

Usage, from the backend directory with the deployment's environment:

    python -m src.management.backfill chunks [--missing-only]

`chunks` reads each transcript-ready video's transcript from S3 and stores its
searchable passages. With --missing-only, videos that already have passages
are skipped, so an interrupted run can resume.
"""

import argparse
import logging

from sqlalchemy import exists, select

from src import database, transcripts
from src.model_registry import import_models
from src.search.chunks import replace_chunks
from src.search.models import TranscriptChunk
from src.videos.models import Video

logger = logging.getLogger("vidwiz.backfill")


def backfill_chunks(missing_only: bool) -> None:
    db = database.SessionLocal()
    try:
        query = select(Video.video_id).where(Video.transcript_available.is_(True))
        if missing_only:
            query = query.where(
                ~exists().where(TranscriptChunk.video_id == Video.video_id)
            )
        video_ids = db.execute(query.order_by(Video.id)).scalars().all()
        stored = missing = 0
        for index, video_id in enumerate(video_ids, start=1):
            transcript = transcripts.load_transcript(video_id)
            if not transcript:
                missing += 1
                continue
            replace_chunks(db, video_id, transcript)
            db.commit()
            stored += 1
            if index % 25 == 0:
                logger.info("Chunked %d of %d videos", index, len(video_ids))
        logger.info(
            "Chunk backfill done: videos=%d stored=%d missing_transcript=%d",
            len(video_ids),
            stored,
            missing,
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="VidWiz v3 backfills")
    commands = parser.add_subparsers(dest="command", required=True)
    chunks = commands.add_parser("chunks", help="Store transcript passages for search")
    chunks.add_argument("--missing-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import_models()
    if args.command == "chunks":
        backfill_chunks(args.missing_only)


if __name__ == "__main__":
    main()
