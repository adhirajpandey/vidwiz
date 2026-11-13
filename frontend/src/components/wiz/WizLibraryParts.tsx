import { useState } from 'react';
import type { DataMessagePartProps } from '@assistant-ui/react';
import type { DigestPart, StatsPart } from '../../api/messageParts';
import { plural, videoTitle } from '../../lib/format';
import { WatchMoment } from './WizCitation';

/** Videos shown before the rest of a digest folds behind a control. */
const VISIBLE_VIDEOS = 5;

function day(value: string, withYear: boolean): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', timeZone: 'UTC', ...(withYear ? { year: 'numeric' } : {}),
  });
}

function period(since: string, until: string): string {
  if (since === until) return day(until, true);
  return `${day(since, since.slice(0, 4) !== until.slice(0, 4))} to ${day(until, true)}`;
}

/** Every moment captured in a period, grouped by video, under the answer. */
export function WizDigest(props: DataMessagePartProps<DigestPart>) {
  // The runtime types part data loosely; name what the part carries.
  const data: DigestPart = props.data;
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? data.videos : data.videos.slice(0, VISIBLE_VIDEOS);
  const folded = data.videos.length - shown.length;
  const unlisted = data.video_count - data.videos.length;
  return (
    <section className="wiz-digest">
      <p className="wiz-digest-head">
        {plural(data.total_moments, 'moment')} from {plural(data.video_count, 'video')}, {period(data.since, data.until)}
      </p>
      <ul>
        {shown.map(video => {
          const title = videoTitle(video.title, video.video_id);
          const missing = video.moment_count - video.moments.length;
          return (
            <li key={video.video_id} className="wiz-digest-video">
              <p className="wiz-digest-title">
                <span>{title}</span>
                <span className="wiz-digest-count">{plural(video.moment_count, 'moment')}</span>
              </p>
              <ul>
                {video.moments.map(moment => (
                  <li key={moment.id} className="wiz-digest-moment">
                    <WatchMoment videoId={video.video_id} video={title} seconds={moment.at_seconds} />
                    <span>{moment.text}</span>
                  </li>
                ))}
              </ul>
              {missing > 0 && <p className="wiz-digest-note">{plural(missing, 'more moment')} not shown</p>}
            </li>
          );
        })}
      </ul>
      {folded > 0 && (
        <button type="button" className="wiz-digest-more" onClick={() => setExpanded(true)}>
          Show {plural(folded, 'more video')}
        </button>
      )}
      {unlisted > 0 && folded === 0 && <p className="wiz-digest-note">{plural(unlisted, 'more video')} not listed</p>}
    </section>
  );
}

const GROUP_LABEL = { channel: 'Channel', month: 'Month' };

/** One video count, or counts grouped by channel or month. */
export function WizStats(props: DataMessagePartProps<StatsPart>) {
  const data: StatsPart = props.data;
  if (data.groups && data.groups.length > 0) {
    return (
      <table className="wiz-stats">
        <thead>
          <tr><th scope="col">{data.group_by ? GROUP_LABEL[data.group_by] : 'Group'}</th><th scope="col">Videos</th></tr>
        </thead>
        <tbody>
          {data.groups.map((group, index) => <tr key={`${index}:${group.name}`}><td>{group.name}</td><td>{group.videos}</td></tr>)}
        </tbody>
      </table>
    );
  }
  return <p className="wiz-stats-line">{plural(data.video_count ?? 0, 'video')}</p>;
}
