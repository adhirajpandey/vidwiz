import { useQuery } from '@tanstack/react-query';
import { libraryApi } from '../../api';
import type { LibraryParams } from '../../api';

export function useLibrary(params: LibraryParams) {
  return useQuery({
    queryKey: ['library', params],
    queryFn: () => libraryApi.list(params),
    placeholderData: previous => previous,
  });
}
