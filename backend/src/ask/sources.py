"""Sources a library answer can cite: transcript passages and moments."""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from src.conversations.parts import CitationPart
from src.moments.models import Moment
from src.moments.schemas import MomentRead


@dataclass(frozen=True)
class Source:
    source_id: str
    video_id: str
    video_title: str | None
    kind: str
    start_seconds: float
    end_seconds: float
    text: str
    # The user's local capture date; moments only.
    captured: date | None = None
    # The video's channel, when the caller looked it up.
    channel: str | None = None

    def citation(self) -> CitationPart:
        return CitationPart(
            type="citation",
            chunk_id=self.source_id,
            start_seconds=self.start_seconds,
            end_seconds=self.end_seconds,
            video_id=self.video_id,
        )

    def context(self) -> dict:
        context = {
            "id": self.source_id,
            "kind": self.kind,
            "video": self.video_title or self.video_id,
            "start_seconds": self.start_seconds,
            "text": self.text,
        }
        if self.captured:
            context["captured"] = self.captured.isoformat()
        return context


def moment_text(moment: MomentRead | Moment) -> str:
    lines = [
        f"User note: {moment.note}" if moment.note else None,
        f"AI line: {moment.ai_text}" if moment.ai_text else None,
        f"Said in the video: {moment.quote}" if moment.quote else None,
    ]
    return "\n".join(line for line in lines if line)


def moment_source(
    moment: MomentRead | Moment,
    video_title: str | None,
    time_zone: str,
    channel: str | None = None,
) -> Source:
    return Source(
        source_id=f"m{moment.id}",
        video_id=moment.video_id,
        video_title=video_title,
        kind="moment",
        start_seconds=moment.at_seconds,
        end_seconds=moment.at_seconds,
        text=moment_text(moment),
        captured=moment.created_at.astimezone(ZoneInfo(time_zone)).date(),
        channel=channel,
    )
