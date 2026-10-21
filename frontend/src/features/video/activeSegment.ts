import type { TranscriptSegment } from '../../api';

/** Index of the segment playing at `seconds`, or -1. */
export function activeSegment(segments: TranscriptSegment[], seconds: number | null): number {
  if (seconds === null) return -1;
  let found = -1;
  for (let index = 0; index < segments.length; index += 1) {
    if (segments[index].start_seconds <= seconds) found = index;
    else break;
  }
  return found;
}
