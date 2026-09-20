import { useState } from "react";
import { Link } from "react-router-dom";
import { Clock3, FileText, Sparkles, Video } from "lucide-react";
import type { VideoSearchItem } from "../api/types";
import Highlight from "./Highlight";

const viewFormatter = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

function uploadDate(value?: string) {
  if (!value || !/^\d{8}$/.test(value)) return "";
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(4, 6));
  const day = Number(value.slice(6, 8));
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) return "";
  return date.toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}

function durationLabel(seconds?: number) {
  if (seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = String(total % 60).padStart(2, "0");
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${remainder}`
    : `${minutes}:${remainder}`;
}

function activityAge(value: string) {
  const days = Math.max(
    0,
    Math.floor((Date.now() - Date.parse(value)) / 86400000),
  );
  if (!Number.isFinite(days)) return "";
  if (days === 0) return "today";
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
  const duration = video.metadata?.duration_string || durationLabel(video.metadata?.duration);
  const views = video.metadata?.view_count;
  const uploaded = uploadDate(video.metadata?.upload_date);
  const metadata = [
    typeof views === "number" && Number.isFinite(views) && views >= 0
      ? `${viewFormatter.format(views)} views` : "",
    uploaded ? `Uploaded ${uploaded}` : "",
  ].filter(Boolean);
  const activity = video.last_activity_at ? activityAge(video.last_activity_at) : "";
  const details = metadata.length > 0 ? (
    <p className="library-video-details">
      {metadata.map((detail) => <span key={detail}>{detail}</span>)}
    </p>
  ) : null;
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
        {duration && (
          <span>{duration}</span>
        )}
      </a>
      <div className="library-video-title">
        <Link
          className={featured ? undefined : "library-row-link"}
          to={`/dashboard/${video.video_id}`}
          title={title}
        >
          <Highlight text={title} query={query} />
        </Link>
        <p className="library-video-channel">
          {video.metadata?.channel ||
            video.metadata?.uploader ||
            "Unknown channel"}
        </p>
        {!featured && details}
      </div>
      {featured && details}
      {!featured && <div className="library-video-meta">
        <span>
          <FileText size={15} />
          {video.note_count ?? 0} {video.note_count === 1 ? "note" : "notes"}
        </span>
        {activity && video.last_activity_at && (
          <span
            title={`Latest note or chat activity: ${new Date(video.last_activity_at).toLocaleString()}`}
          >
            <Clock3 size={15} />
            Active {activity}
          </span>
        )}
      </div>}
      <div className="library-video-actions">
        <Link
          className="library-button library-button-notes"
          to={`/dashboard/${video.video_id}`}
        >
          <FileText size={15} />
          View notes
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
