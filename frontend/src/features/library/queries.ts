import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { libraryApi } from '../../api';
import type { LibraryParams } from '../../api';
import { momentKeys } from '../moments/queries';

export function useLibrary(params: LibraryParams) {
  return useQuery({
    queryKey: ['library', params],
    queryFn: () => libraryApi.list(params),
    placeholderData: previous => previous,
  });
}

/** Deleting a video also deletes its moments and chats, so those lists refresh too. */
export function useRemoveVideo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (videoId: string) => libraryApi.remove(videoId),
    onSuccess: (_result, videoId) => {
      void queryClient.invalidateQueries({ queryKey: ['library'] });
      void queryClient.invalidateQueries({ queryKey: momentKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['search'] });
      void queryClient.invalidateQueries({ queryKey: ['conversations', 'video', videoId] });
    },
  });
}
