import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { momentsApi, videosApi } from '../../api';
import { hasPendingWork, momentKeys } from '../moments/queries';
import { videoHasPendingWork } from './status';

// Poll while the transcript or overview is still in progress. Every job ends
// in an explicit state, so polling always stops.
const POLL_MS = 5000;

export const videoKeys = {
  video: (videoId: string) => ['video', videoId] as const,
  transcript: (videoId: string) => ['video', videoId, 'transcript'] as const,
  askStatus: (videoId: string) => ['video', videoId, 'ask-status'] as const,
};

export function useVideo(videoId: string) {
  return useQuery({
    queryKey: videoKeys.video(videoId),
    queryFn: () => videosApi.getVideo(videoId),
    refetchInterval: query => (videoHasPendingWork(query.state.data) ? POLL_MS : false),
  });
}

export function useRetryOverview(videoId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => videosApi.retryOverview(videoId),
    onSuccess: video => queryClient.setQueryData(videoKeys.video(videoId), video),
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
    refetchInterval: query => (query.state.data?.status === 'pending' ? POLL_MS : false),
  });
}

export function useAskStatus(videoId: string) {
  return useQuery({ queryKey: videoKeys.askStatus(videoId), queryFn: () => videosApi.getAskStatus(videoId) });
}
