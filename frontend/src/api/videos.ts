import apiClient from './client';
import type {
  VideoListParams,
  VideoListResponse,
  VideoRead,
} from './types';

export const videosApi = {
  getVideo: async (videoId: string) => {
    const response = await apiClient.get<VideoRead>(`/videos/${videoId}`);
    return response.data;
  },

  listVideos: async (params: VideoListParams = {}) => {
    const response = await apiClient.get<VideoListResponse>('/videos', {
      params,
    });
    return response.data;
  },

  getStreamUrl: (videoId: string) => {
    // Return relative URL for EventSource usage
    return `/videos/${videoId}/stream`;
  },
};
