import type { VideoRead } from '../../api';

/** The transcript or overview is still being produced, so the page polls. */
export function videoHasPendingWork(video: VideoRead | undefined): boolean {
  if (!video) return false;
  return video.transcript_status === 'pending' || video.overview_status === 'queued';
}
