import { useMutation, useQueryClient } from '@tanstack/react-query';
import { momentsApi } from '../../api';
import type { MomentRead, MomentUpdate, PassageSave } from '../../api';
import { PROFILE_KEY } from '../../hooks/useProfile';

export const momentKeys = {
  all: ['moments'] as const,
  feed: ['moments', 'feed'] as const,
  video: (videoId: string) => ['moments', 'video', videoId] as const,
};

/** Moment changes can affect the feed, a video's list, and the library counts. */
function useInvalidateMoments() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: momentKeys.all });
    void queryClient.invalidateQueries({ queryKey: ['library'] });
  };
}

export function useUpdateMoment() {
  const invalidate = useInvalidateMoments();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: MomentUpdate }) => momentsApi.update(id, body),
    onSuccess: invalidate,
  });
}

export function useDeleteMoment() {
  const invalidate = useInvalidateMoments();
  return useMutation({ mutationFn: (id: number) => momentsApi.remove(id), onSuccess: invalidate });
}

export function useRequestAi() {
  const invalidate = useInvalidateMoments();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => momentsApi.requestAi(id),
    onSuccess: () => {
      invalidate();
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
    },
  });
}

export function useResolveMoment() {
  const invalidate = useInvalidateMoments();
  return useMutation({
    mutationFn: ({ id, videoId }: { id: number; videoId: string }) => momentsApi.resolve(id, videoId),
    onSuccess: invalidate,
  });
}

export function useSavePassage() {
  const invalidate = useInvalidateMoments();
  return useMutation({ mutationFn: (body: PassageSave) => momentsApi.savePassage(body), onSuccess: invalidate });
}

/** Moments still waiting on background work, so lists keep polling. */
export function hasPendingWork(moments: MomentRead[] | undefined): boolean {
  return Boolean(moments?.some(moment =>
    moment.resolve_status === 'resolving' ||
    moment.ai_status === 'queued' ||
    moment.ai_status === 'waiting_transcript'));
}

export function startSeconds(moment: MomentRead): number {
  return moment.quote_start_seconds ?? moment.at_seconds;
}
