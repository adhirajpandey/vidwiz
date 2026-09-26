import { apiRequest } from './fetch';
import type {
  LibrarySummary,
  VideoListParams,
  VideoListResponse,
  VideoRead,
} from './types';

export const videosApi = {
  librarySummary: () =>
    apiRequest<LibrarySummary>('GET', '/videos/library-summary'),
  getVideo: (videoId: string) =>
    apiRequest<VideoRead>('GET', `/videos/${videoId}`),
  listVideos: (params: VideoListParams = {}) =>
    apiRequest<VideoListResponse>('GET', '/videos', { params: { ...params } }),
  // Streaming responses are read with apiFetch directly.
  getStreamUrl: (videoId: string) => `/videos/${videoId}/stream`,
};
