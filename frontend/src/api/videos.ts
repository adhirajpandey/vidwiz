import { apiRequest } from './fetch';
import type { TranscriptRead, VideoRead } from './types';

export interface AskStatus {
  unlocked: boolean;
  /** Credits charged when the first conversation for the video starts. */
  cost: number;
}

export const videosApi = {
  getVideo: (videoId: string) => apiRequest<VideoRead>('GET', `/videos/${videoId}`),
  getAskStatus: (videoId: string) =>
    apiRequest<AskStatus>('GET', `/videos/${videoId}/ask-status`),
  getTranscript: (videoId: string) =>
    apiRequest<TranscriptRead>('GET', `/videos/${videoId}/transcript`),
  // Streaming responses are read with apiFetch directly.
  getStreamUrl: (videoId: string) => `/videos/${videoId}/stream`,
};
