import { apiRequest } from './fetch';
import type {
  CaptureCreate,
  CaptureResponse,
  MomentFeed,
  MomentRead,
  MomentUpdate,
  PassageSave,
  ResurfaceResponse,
} from './types';

export const momentsApi = {
  resurface: (skip = 0) => apiRequest<ResurfaceResponse>('GET', '/moments/resurface', { params: { skip } }),
  capture: (body: CaptureCreate) =>
    apiRequest<CaptureResponse>('POST', '/captures', { body }),
  feed: (page = 1, perPage = 20) =>
    apiRequest<MomentFeed>('GET', '/moments', { params: { page, per_page: perPage } }),
  forVideo: (videoId: string) =>
    apiRequest<MomentRead[]>('GET', `/videos/${videoId}/moments`),
  update: (momentId: number, body: MomentUpdate) =>
    apiRequest<MomentRead>('PATCH', `/moments/${momentId}`, { body }),
  remove: (momentId: number) =>
    apiRequest<{ message: string }>('DELETE', `/moments/${momentId}`),
  requestAi: (momentId: number) =>
    apiRequest<MomentRead>('POST', `/moments/${momentId}/ai`),
  resolve: (momentId: number, videoId: string) =>
    apiRequest<MomentRead>('POST', `/moments/${momentId}/resolve`, {
      body: { video_id: videoId },
    }),
  savePassage: (body: PassageSave) =>
    apiRequest<CaptureResponse>('POST', '/moments/passages', { body }),
};
