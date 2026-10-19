import { apiRequest } from './fetch';
import type { SearchResponse } from './types';

export const searchApi = {
  search: (q: string, params: { page?: number; per_page?: number; video_id?: string } = {}) =>
    apiRequest<SearchResponse>('GET', '/search', { params: { q, ...params } }),
};
