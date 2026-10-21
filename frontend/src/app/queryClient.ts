import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../api';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      // Client errors will not succeed on retry; network and 5xx errors might.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.response.status < 500) && failureCount < 2,
    },
  },
});
