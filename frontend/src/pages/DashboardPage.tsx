import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  FileText,
  MessageSquare,
  Search,
  Sparkles,
  Youtube,
} from "lucide-react";
import { videosApi, notesApi } from "../api";
import { normalizeApiError } from "../api/errors";
import type { NormalizedApiError } from "../api/errors";
import type { VideoListParams } from "../api/types";
import VideoCard from "../components/VideoCard";
import LibraryDropdown from "../components/LibraryDropdown";
import LibrarySort from "../components/LibrarySort";
import Highlight from "../components/Highlight";
import ErrorState from "../components/ui/ErrorState";
import Seo from "../components/Seo";
import config from "../config";
import "./dashboard.css";

const searchScopes = [
  { value: "all", label: "All" },
  { value: "videos", label: "Videos" },
  { value: "notes", label: "Notes" },
] as const;

function useResource<T>(key: string, fetcher: () => Promise<T>) {
  const [attempt, retry] = useState(0);
  const [result, setResult] = useState<{
    key: string;
    attempt: number;
    data?: T;
    error?: NormalizedApiError;
  }>();
  useEffect(() => {
    let active = true;
    fetcher()
      .then((data) => {
        if (active) setResult({ key, attempt, data });
      })
      .catch((error) => {
        if (active)
          setResult({
            key,
            attempt,
            error: normalizeApiError(
              error,
              "Unable to load this section. Please try again.",
            ),
          });
      });
    return () => {
      active = false;
    };
    // The key describes every request parameter; fetcher is intentionally not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);
  return {
    data:
      result?.key === key && result.attempt === attempt
        ? result.data
        : undefined,
    error:
      result?.key === key && result.attempt === attempt
        ? result.error
        : undefined,
    retry: () => retry((value) => value + 1),
  };
}

function Pagination({
  page,
  pages,
  onChange,
  label,
}: {
  page: number;
  pages: number;
  onChange: (page: number) => void;
  label: string;
}) {
  if (pages <= 1 && page <= 1) return null;
  return (
    <nav aria-label={`${label} pagination`} className="library-pagination">
      <button
        className="library-button library-button-muted"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </button>
      <span>
        Page {page} of {Math.max(1, pages)}
      </span>
      <button
        className="library-button library-button-muted"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </nav>
  );
}

function Loading() {
  return (
    <div role="status" aria-label="Loading" className="library-loading">
      <div />
      <div />
      <div />
    </div>
  );
}
function Failure({
  error,
  retry,
}: {
  error: NormalizedApiError;
  retry: () => void;
}) {
  return (
    <ErrorState
      compact
      title="Unable to load this section"
      message={error.message}
      referenceId={error.requestId}
      onRetry={retry}
    />
  );
}
function pageNumber(value: string | null) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : 1;
}

export default function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const query = (params.get("q") || "").trim();
  const searching = query.length >= 2;
  const scopeParam = params.get("scope");
  const scope = scopeParam === "videos" || scopeParam === "notes" ? scopeParam : "all";
  const showVideos = !searching || scope !== "notes";
  const showNotes = searching && scope !== "videos";
  const videoPage = pageNumber(params.get("videosPage"));
  const notePage = pageNumber(params.get("notesPage"));
  const selectedSort = params.get("sort");
  const sort: VideoListParams["sort"] =
    !searching &&
    (selectedSort === "title_asc" || selectedSort === "title_desc")
      ? selectedSort
      : "activity_desc";
  const [draft, setDraft] = useState(query);
  const [validation, setValidation] = useState("");
  useEffect(() => {
    setDraft(query);
  }, [query]);
  const summary = useResource("summary", videosApi.librarySummary);
  const videos = useResource(`videos:${query}:${videoPage}:${sort}:${showVideos}`, () =>
    showVideos ? videosApi.listVideos({
      q: searching ? query : "",
      page: videoPage,
      per_page: 10,
      sort,
    }) : Promise.resolve(null),
  );
  const notes = useResource(`notes:${query}:${notePage}:${showNotes}`, () =>
    showNotes ? notesApi.search(query, notePage) : Promise.resolve(null),
  );
  function changePage(key: string, page: number) {
    const next = new URLSearchParams(params);
    next.set(key, String(page));
    setParams(next);
  }
  function clear() {
    setDraft("");
    setValidation("");
    setParams(scope === "all" ? {} : { scope });
  }
  const counts = [
    { label: "videos", value: summary.data?.videos, Icon: Youtube },
    { label: "notes", value: summary.data?.notes, Icon: FileText },
    { label: "AI notes", value: summary.data?.ai_notes, Icon: Sparkles },
    { label: "Wiz chats", value: summary.data?.wiz_chats, Icon: MessageSquare },
  ];
  return (
    <>
      <Seo
        title="Your library | VidWiz"
        description="Your saved YouTube videos, notes and AI insights."
        path="/dashboard"
        noIndex
      />
      <div className="library-dashboard">
        <header className="library-header">
          <div>
            <h1>Your library</h1>
            <p>
              All your saved YouTube videos, notes and AI insights in one place.
            </p>
          </div>
          <div className="library-stats" aria-label="Library totals">
            {counts.map(({ label, value, Icon }) => (
              <div className="library-stat" key={label}>
                <Icon size={23} />
                <div>
                  <strong>
                    {value === undefined ? "—" : value.toLocaleString()}
                  </strong>
                  <span>{label}</span>
                </div>
              </div>
            ))}
          </div>
        </header>
        {summary.error && (
          <Failure error={summary.error} retry={summary.retry} />
        )}
        <form
          className="library-search"
          onSubmit={(event) => {
            event.preventDefault();
            const q = draft.trim();
            if (!q) {
              clear();
              return;
            }
            if (q.length < 2) {
              setValidation("Enter at least two characters to search.");
              return;
            }
            setValidation("");
            setParams(scope === "all" ? { q } : { q, scope });
          }}
        >
          <div className="library-search-scope">
            <LibraryDropdown label="Search scope" options={searchScopes} value={scope} onChange={(value) => {
              const next = new URLSearchParams(params);
              if (value === "all") next.delete("scope");
              else next.set("scope", value);
              next.delete("videosPage");
              next.delete("notesPage");
              setParams(next);
            }} />
          </div>
          <div className="library-search-field">
          <Search size={18} aria-hidden="true" />
          <input
            aria-label="Search videos and notes"
            aria-describedby={validation ? "search-guidance" : undefined}
            value={draft}
            maxLength={500}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={scope === "videos" ? "Search video titles…" : scope === "notes" ? "Search notes…" : "Search videos and notes…"}
          />
          {(query || draft) && (
            <button type="button" className="library-clear" onClick={clear}>
              Clear
            </button>
          )}
          </div>
          <button
            className="library-button library-button-primary"
            type="submit"
          >
            <Search size={16} />
            Search
          </button>
        </form>
        {validation && (
          <p
            id="search-guidance"
            role="alert"
            className="text-red-500 text-sm mb-5"
          >
            {validation}
          </p>
        )}
        {!searching && !!summary.data?.recent_videos.length && (
          <section className="library-recent" aria-labelledby="recent-heading">
            <div className="library-section-heading">
              <div>
                <h2 id="recent-heading">Recent activity</h2>
                <p>Revisit your latest notes and chats.</p>
              </div>
            </div>
            <div className="library-featured-grid">
              {summary.data.recent_videos.map((video) => (
                <VideoCard key={video.video_id} video={video} featured />
              ))}
            </div>
          </section>
        )}
        {!searching && !summary.data && !summary.error && <Loading />}
        {showVideos && <section
          id="library"
          aria-labelledby="library-heading"
          className="library-section"
        >
          <div className="library-section-heading">
            <div className={searching ? undefined : "sr-only"}>
              <h2 id="library-heading">
                {searching ? "Videos" : "Saved videos"}
                {searching && videos.data ? ` (${videos.data.total})` : ""}
              </h2>
              <p>
                {searching
                  ? `Title matches for “${query}”`
                  : "A list of all your saved videos."}
              </p>
            </div>
            {!searching && (
              <LibrarySort value={sort} onChange={(value) => {
                const next = new URLSearchParams(params);
                next.set("sort", value);
                next.delete("videosPage");
                setParams(next);
              }} />
            )}
          </div>
          {videos.error ? (
            <Failure error={videos.error} retry={videos.retry} />
          ) : !videos.data ? (
            <Loading />
          ) : (
            <>
              {videos.data.videos.length ? (
                <div className="library-rows">
                  {videos.data.videos.map((video) => (
                    <VideoCard
                      key={video.video_id}
                      video={video}
                      query={searching ? query : ""}
                    />
                  ))}
                </div>
              ) : (
                <div className="library-empty">
                  <h3>
                    {searching
                      ? "No matching videos"
                      : videoPage > 1
                        ? "No videos on this page"
                        : "Start your library"}
                  </h3>
                  <p>
                    {searching
                      ? scope === "videos" ? "Try another video title." : "Try another title, or check the note matches below."
                      : videoPage > 1
                        ? "Return to a previous page."
                        : "Install the Chrome extension, open a YouTube video, and save your first note."}
                  </p>
                  {!searching && videoPage === 1 && (
                    <>
                      <a
                        className="library-button library-button-primary"
                        href={config.CHROME_WEBSTORE_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Install Chrome Extension <ArrowRight size={16} />
                      </a>
                      <Link to="/help">See how it works</Link>
                    </>
                  )}
                </div>
              )}
              <Pagination
                label="Videos"
                page={videoPage}
                pages={videos.data.total_pages}
                onChange={(page) => changePage("videosPage", page)}
              />
            </>
          )}
        </section>}
        {showNotes && (
          <section className="library-section" aria-labelledby="notes-heading">
            <div className="library-section-heading">
              <div>
                <h2 id="notes-heading">
                  Notes{notes.data ? ` (${notes.data.total})` : ""}
                </h2>
                <p>Matches in your saved notes</p>
              </div>
            </div>
            {notes.error ? (
              <Failure error={notes.error} retry={notes.retry} />
            ) : !notes.data ? (
              <Loading />
            ) : (
              <>
                {notes.data.notes.length ? (
                  <div className="library-rows">
                    {notes.data.notes.map((note) => (
                      <article key={note.id} className="library-note-result">
                        <div>
                          <h3>
                            {note.title ||
                              note.metadata?.title ||
                              "Untitled video"}
                          </h3>
                          <div className="library-note-meta">
                            <span>{note.timestamp}</span>
                            {note.generated_by_ai && (
                              <span>
                                <Sparkles size={13} />
                                AI note
                              </span>
                            )}
                          </div>
                          <p>
                            <Highlight text={note.excerpt} query={query} />
                          </p>
                        </div>
                        <Link
                          className="library-button library-button-notes"
                          to={`/dashboard/${note.video_id}#note-${note.id}`}
                        >
                          <FileText size={15} /> Open note
                        </Link>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="library-empty">
                    <h3>No matching notes</h3>
                    <p>Try another word or phrase.</p>
                  </div>
                )}
                <Pagination
                  label="Notes"
                  page={notePage}
                  pages={notes.data.total_pages}
                  onChange={(page) => changePage("notesPage", page)}
                />
              </>
            )}
          </section>
        )}
      </div>
    </>
  );
}
