import { useQuery } from '@tanstack/react-query';
import { momentsApi, videosApi } from '../../api';
import { hasPendingWork, momentKeys } from '../moments/queries';

// Background work (metadata, transcript, overview) usually lands within a
// couple of minutes; stop polling after that so a failed job does not poll forever.
const POLL_MS = 5000;
const MAX_POLLS = 40;

export const videoKeys = {
  video: (videoId: string) => ['video', videoId] as const,
  transcript: (videoId: string) => ['video', videoId, 'transcript'] as const,
  askStatus: (videoId: string) => ['video', videoId, 'ask-status'] as const,
};

export function useVideo(videoId: string) {
  return useQuery({
    queryKey: videoKeys.video(videoId),
    queryFn: () => videosApi.getVideo(videoId),
    refetchInterval: query => {
      const video = query.state.data;
      const done = video && video.metadata && video.transcript_available && video.key_points;
      return done || query.state.dataUpdateCount > MAX_POLLS ? false : POLL_MS;
    },
  });
}

export function useVideoMoments(videoId: string, enabled: boolean) {
  return useQuery({
    queryKey: momentKeys.video(videoId),
    queryFn: () => momentsApi.forVideo(videoId),
    enabled,
    refetchInterval: query => (hasPendingWork(query.state.data) ? POLL_MS : false),
  });
}

export function useTranscript(videoId: string, enabled: boolean) {
  return useQuery({
    queryKey: videoKeys.transcript(videoId),
    queryFn: () => videosApi.getTranscript(videoId),
    enabled,
    refetchInterval: query =>
      query.state.data?.status === 'processing' && query.state.dataUpdateCount <= MAX_POLLS ? POLL_MS : false,
  });
}

export function useAskStatus(videoId: string) {
  return useQuery({ queryKey: videoKeys.askStatus(videoId), queryFn: () => videosApi.getAskStatus(videoId) });
}
