"""One-time data backfills for v3.

Usage, from the backend directory with the deployment's environment:

    python -m src.management.backfill chunks [--missing-only]
    python -m src.management.backfill overviews --limit N
    python -m src.management.backfill quotes [--all]

`chunks` reads each transcript-ready video's transcript from S3 and stores its
searchable passages. With --missing-only, videos that already have passages
are skipped, so an interrupted run can resume.

`overviews` queues up to N overviews, most recently used videos first: those
never written, failed, or written before key points existed. Videos whose
transcript is not in the bucket yet are skipped. Each overview costs model
usage, so batches stay small.

`quotes` fills the quote of every moment that has none on a transcript-ready
video. Moments imported from v2 arrive after their transcripts, so the
transcript-stored hook never filled them. Run it after each data import.
With --all, recompute existing quotes too. Neither mode changes updated_at.
"""

import argparse
import logging

from sqlalchemy import exists, select

from src import database, transcripts
from src.model_registry import import_models
from src.moments import service as moments_service
from src.moments.models import Moment
from src.search.chunks import replace_chunks
from src.search.models import TranscriptChunk
from src.videos import overview
from src.videos.models import OverviewStatus, TranscriptStatus, Video

logger = logging.getLogger("vidwiz.backfill")


def backfill_chunks(missing_only: bool) -> None:
    db = database.SessionLocal()
    try:
        query = select(Video.video_id).where(
            Video.transcript_status == TranscriptStatus.READY
        )
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


def backfill_overviews(limit: int) -> None:
    db = database.SessionLocal()
    try:
        queued = missing = 0
        for video in overview.backfill_candidates(db, limit):
            if not transcripts.load_transcript(video.video_id):
                missing += 1
                continue
            overview.queue(db, video)
            queued += video.overview_status == OverviewStatus.QUEUED
        logger.info(
            "Overview backfill done: queued=%d missing_transcript=%d", queued, missing
        )
    finally:
        db.close()


def backfill_quotes(recompute_all: bool = False) -> None:
    db = database.SessionLocal()
    try:
        query = (
            select(Moment.video_id)
            .join(Video, Video.video_id == Moment.video_id)
            .where(Video.transcript_status == TranscriptStatus.READY)
        )
        if not recompute_all:
            query = query.where(Moment.quote.is_(None))
        video_ids = (
            db.execute(query.distinct().order_by(Moment.video_id)).scalars().all()
        )
        filled = missing = 0
        for index, video_id in enumerate(video_ids, start=1):
            transcript = transcripts.load_transcript(video_id)
            if not transcript:
                missing += 1
                continue
            moments_service.on_transcript_stored(
                db, video_id, transcript, recompute_all=recompute_all
            )
            db.commit()
            filled += 1
            if index % 25 == 0:
                logger.info("Filled quotes on %d of %d videos", index, len(video_ids))
        logger.info(
            "Quote backfill done: videos=%d filled=%d missing_transcript=%d",
            len(video_ids),
            filled,
            missing,
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="VidWiz v3 backfills")
    commands = parser.add_subparsers(dest="command", required=True)
    chunks = commands.add_parser("chunks", help="Store transcript passages for search")
    chunks.add_argument("--missing-only", action="store_true")
    overviews = commands.add_parser("overviews", help="Queue overviews in a batch")
    overviews.add_argument("--limit", type=int, required=True)
    quotes = commands.add_parser("quotes", help="Fill missing moment quotes")
    quotes.add_argument(
        "--all", action="store_true", help="Recompute existing quotes too"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import_models()
    if args.command == "chunks":
        backfill_chunks(args.missing_only)
    elif args.command == "overviews":
        backfill_overviews(args.limit)
    elif args.command == "quotes":
        backfill_quotes(recompute_all=args.all)


if __name__ == "__main__":
    main()
