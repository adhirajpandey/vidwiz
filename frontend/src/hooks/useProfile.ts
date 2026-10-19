import { useQuery } from '@tanstack/react-query';
import { authApi } from '../api';
import { useSignedIn } from './useSignedIn';

export const PROFILE_KEY = ['profile'] as const;

/** The signed-in user's profile, including the credit balance. */
export function useProfile() {
  const signedIn = useSignedIn();
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: authApi.getMe,
    enabled: signedIn,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}
