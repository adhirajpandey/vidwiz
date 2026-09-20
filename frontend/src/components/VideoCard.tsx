import { useState } from "react";
import { Link } from "react-router-dom";
import { Clock3, FileText, Sparkles, Video } from "lucide-react";
import type { VideoSearchItem } from "../api/types";
import Highlight from "./Highlight";

function activityAge(value: string) {
  const days = Math.max(
    0,
    Math.floor((Date.now() - Date.parse(value)) / 86400000),
  );
  if (!Number.isFinite(days)) return "";
  if (days === 0) return "Today";
  if (days < 7) return `${days} ${days === 1 ? "day" : "days"} ago`;
  if (days < 30)
    return `${Math.floor(days / 7)} ${days < 14 ? "week" : "weeks"} ago`;
  return new Date(value).toLocaleDateString();
}

export default function VideoCard({
  video,
  featured = false,
  query = "",
}: {
  video: VideoSearchItem;
  featured?: boolean;
  query?: string;
}) {
  const [failed, setFailed] = useState(false);
  const title = video.title || video.metadata?.title || "Untitled video";
  const thumbnail =
    video.metadata?.thumbnail ||
    `https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`;
  return (
    <article
      className={`library-video ${featured ? "library-video-featured" : ""}`}
    >
      <a
        className="library-thumbnail"
        href={`https://www.youtube.com/watch?v=${video.video_id}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Watch ${title} on YouTube`}
      >
        {failed ? (
          <Video className="m-auto text-muted-foreground" />
        ) : (
          <img
            src={thumbnail}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
          />
        )}
        {video.metadata?.duration_string && (
          <span>{video.metadata.duration_string}</span>
        )}
      </a>
      <div className="library-video-title">
        <Link to={`/dashboard/${video.video_id}`}>
          <Highlight text={title} query={query} />
        </Link>
        <p>
          {video.metadata?.channel ||
            video.metadata?.uploader ||
            "Unknown channel"}
        </p>
      </div>
      <div className="library-video-meta">
        <span>
          <FileText size={15} />
          {video.note_count ?? 0} notes
        </span>
        {video.last_activity_at && (
          <span
            title={`Latest note or chat activity: ${new Date(video.last_activity_at).toLocaleString()}`}
          >
            <Clock3 size={15} />
            {activityAge(video.last_activity_at)}
          </span>
        )}
      </div>
      <div className="library-video-actions">
        <Link
          className={
            featured
              ? "library-button library-button-muted"
              : "library-button library-button-primary"
          }
          to={`/dashboard/${video.video_id}`}
        >
          <FileText size={15} />
          {featured ? "Notes" : "View notes"}
        </Link>
        <Link
          className="library-button library-button-wiz"
          to={`/wiz/${video.video_id}`}
        >
          <Sparkles size={16} />
          Ask Wiz
        </Link>
      </div>
    </article>
  );
}
