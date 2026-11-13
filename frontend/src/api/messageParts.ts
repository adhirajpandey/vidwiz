export type TextPart = { type: 'text'; text: string };
/** video_id is set in library answers, where sources span videos; null within one video. */
export type Passage = {
  chunk_ids: string[];
  start_seconds: number;
  end_seconds: number;
  video_id?: string | null;
};
export type BlockCitation = { list_item_index: number | null; passages: Passage[] };
export type BlockPart = { type: 'block'; text: string; citations: BlockCitation[] };
export type CitationPart = {
  type: 'citation';
  chunk_id: string;
  start_seconds: number;
  end_seconds: number;
};
export type DigestMoment = { id: string; at_seconds: number; text: string };
/** `moments` may hold fewer entries than `moment_count`. */
export type DigestVideo = { video_id: string; title: string | null; moment_count: number; moments: DigestMoment[] };
/** Every moment the user captured from `since` to `until` (YYYY-MM-DD), grouped by video. */
export type DigestPart = {
  type: 'digest';
  since: string;
  until: string;
  total_moments: number;
  video_count: number;
  videos: DigestVideo[];
};
export type StatsGroup = { name: string; videos: number };
/** One video count, or counts grouped by channel or month. */
export type StatsPart = {
  type: 'stats';
  video_count: number | null;
  group_by: 'channel' | 'month' | null;
  groups: StatsGroup[] | null;
};
export type MessagePart = TextPart | CitationPart | BlockPart | DigestPart | StatsPart;
/** A progress line shown until the answer has content. Streamed only, never stored. */
export type StatusEvent = { type: 'status'; text: string };
export type WizStreamEvent = MessagePart | StatusEvent
  | { type: 'done'; message_id: number }
  | { type: 'error'; message: string };

/** Whether a part shows the answer something, as opposed to a bare legacy citation or empty stats. */
export function hasContent(part: MessagePart): boolean {
  if (part.type === 'digest') return true;
  if (part.type === 'stats') return part.video_count !== null || (part.groups?.length ?? 0) > 0;
  return part.type !== 'citation' && part.text.trim().length > 0;
}

/**
 * Validates one stream event. Returns null for an unknown kind or a malformed
 * newer kind (status, digest, stats) so callers skip it; throws for anything
 * else that is malformed.
 */
export function parseWizEvent(value: unknown): WizStreamEvent | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Invalid stream event');
  }
  const data = value as Record<string, unknown>;
  switch (data.type) {
    case 'status':
      return typeof data.text === 'string' && data.text.trim() ? { type: 'status', text: data.text } : null;
    case 'digest':
    case 'stats':
      return newerPart(data);
    case 'block':
      if (typeof data.text === 'string' && Array.isArray(data.citations) && data.citations.every(validCitation)) {
        return { type: 'block', text: data.text, citations: data.citations };
      }
      break;
    case 'text':
      if (typeof data.text === 'string') return { type: 'text', text: data.text };
      break;
    case 'citation':
      if (typeof data.chunk_id === 'string' && data.chunk_id.length > 0 &&
          typeof data.start_seconds === 'number' && Number.isFinite(data.start_seconds) && data.start_seconds >= 0 &&
          typeof data.end_seconds === 'number' && Number.isFinite(data.end_seconds) && data.end_seconds >= data.start_seconds) {
        return { type: 'citation', chunk_id: data.chunk_id, start_seconds: data.start_seconds, end_seconds: data.end_seconds };
      }
      break;
    case 'done':
      if (typeof data.message_id === 'number' && Number.isSafeInteger(data.message_id) && data.message_id > 0) {
        return { type: 'done', message_id: data.message_id };
      }
      break;
    case 'error':
      if (typeof data.message === 'string' && data.message.length > 0) return { type: 'error', message: data.message };
      break;
    default:
      return null;
  }
  throw new Error('Invalid stream event');
}

/**
 * Parts of a stored message. Older kinds are kept as stored; digest and stats
 * are kept only when valid; anything else is ignored.
 */
export function readStoredParts(parts: readonly unknown[]): MessagePart[] {
  return parts.flatMap(part => {
    if (typeof part !== 'object' || part === null) return [];
    const data = part as Record<string, unknown>;
    if (data.type === 'text' || data.type === 'citation' || data.type === 'block') return [part as MessagePart];
    const newer = newerPart(data);
    return newer ? [newer] : [];
  });
}

function newerPart(data: Record<string, unknown>): DigestPart | StatsPart | null {
  if (data.type === 'digest' && isDate(data.since) && isDate(data.until) && isCount(data.total_moments) &&
      isCount(data.video_count) && Array.isArray(data.videos) && data.videos.every(validVideo)) {
    return { type: 'digest', since: data.since, until: data.until, total_moments: data.total_moments, video_count: data.video_count, videos: data.videos };
  }
  if (data.type === 'stats' && (data.video_count === null || isCount(data.video_count)) &&
      (data.group_by === null || data.group_by === 'channel' || data.group_by === 'month') &&
      (data.groups === null || (Array.isArray(data.groups) && data.groups.every(g =>
        g && typeof g === 'object' && typeof g.name === 'string' && isCount(g.videos))))) {
    return { type: 'stats', video_count: data.video_count, group_by: data.group_by, groups: data.groups };
  }
  return null;
}

/** A real calendar day as YYYY-MM-DD: it must survive a UTC round trip unchanged. */
function isDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
const isCount = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;

function validVideo(value: unknown): value is DigestVideo {
  if (!value || typeof value !== 'object') return false;
  const v = value as DigestVideo;
  return typeof v.video_id === 'string' && v.video_id.length > 0 && (v.title === null || typeof v.title === 'string') &&
    isCount(v.moment_count) && Array.isArray(v.moments) && v.moments.every(m =>
      m && typeof m.id === 'string' && m.id.length > 0 && typeof m.text === 'string' &&
      typeof m.at_seconds === 'number' && Number.isFinite(m.at_seconds) && m.at_seconds >= 0);
}

function validCitation(value: unknown): value is BlockCitation {
  if (!value || typeof value !== 'object') return false;
  const c = value as BlockCitation;
  return (c.list_item_index === null || (Number.isSafeInteger(c.list_item_index) && c.list_item_index >= 0)) &&
    Array.isArray(c.passages) && c.passages.length > 0 && c.passages.every(p =>
      p && Array.isArray(p.chunk_ids) && p.chunk_ids.length > 0 && p.chunk_ids.every(id => typeof id === 'string' && id.length > 0) &&
      typeof p.start_seconds === 'number' && Number.isFinite(p.start_seconds) && p.start_seconds >= 0 &&
      typeof p.end_seconds === 'number' && Number.isFinite(p.end_seconds) && p.end_seconds >= p.start_seconds &&
      (p.video_id === undefined || p.video_id === null || typeof p.video_id === 'string'));
}
