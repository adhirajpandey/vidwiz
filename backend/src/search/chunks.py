import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src import transcripts
from src.search.models import TranscriptChunk

logger = logging.getLogger(__name__)


def replace_chunks(db: Session, video_id: str, transcript: list) -> int:
    """Store a video's transcript as searchable passages, replacing old ones."""
    # Flush pending chunks first, so a replaced set is deleted too.
    db.flush()
    db.execute(delete(TranscriptChunk).where(TranscriptChunk.video_id == video_id))
    chunks = transcripts.chunk_transcript(transcript)
    db.add_all(
        TranscriptChunk(
            video_id=video_id,
            idx=index,
            start_seconds=start,
            end_seconds=end,
            text=text,
        )
        for index, (start, end, text) in enumerate(chunks)
    )
    logger.debug(
        "Stored transcript chunks", extra={"video_id": video_id, "count": len(chunks)}
    )
    return len(chunks)
