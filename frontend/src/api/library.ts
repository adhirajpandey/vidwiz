import { apiFetch, ApiError, apiRequest } from './fetch';
import type { LibraryResponse, LibrarySort, LibraryView, MessageResponse } from './types';

export interface LibraryParams {
  q?: string;
  page?: number;
  per_page?: number;
  sort?: LibrarySort;
  view?: LibraryView;
}

async function downloadMarkdown(path: string): Promise<string> {
  const response = await apiFetch(path);
  if (!response.ok) throw new ApiError(response, undefined);
  return response.text();
}

export const libraryApi = {
  list: (params: LibraryParams = {}) =>
    apiRequest<LibraryResponse>('GET', '/library', { params: { ...params } }),
  save: (videoId: string) =>
    apiRequest<MessageResponse>('PUT', `/library/${encodeURIComponent(videoId)}`),
  remove: (videoId: string) =>
    apiRequest<MessageResponse>('DELETE', `/library/${encodeURIComponent(videoId)}`),
  exportLibrary: () => downloadMarkdown('/library/export.md'),
  exportVideo: (videoId: string) => downloadMarkdown(`/videos/${videoId}/export.md`),
};
