import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { libraryApi } from '../../api';
import { useSignedIn } from '../../hooks/useSignedIn';
import PageTitle from '../../components/PageTitle';
import EmptyState from '../../components/ui/EmptyState';
import ErrorState from '../../components/ui/ErrorState';
import Spinner from '../../components/ui/Spinner';
import { sharedVideoId } from './sharedVideoId';

/** PWA share target: sharing a YouTube video to VidWiz saves and opens it. */
export default function SharePage() {
  const [params] = useSearchParams();
  const signedIn = useSignedIn();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [failed, setFailed] = useState(false);
  // Each attempt saves once, so StrictMode and re-renders cannot save twice.
  const [attempt, setAttempt] = useState(0);
  const started = useRef(-1);
  const videoId = sharedVideoId(params);

  useEffect(() => {
    if (!signedIn || !videoId || started.current === attempt) return;
    started.current = attempt;
    libraryApi.save(videoId)
      .then(() => {
        void queryClient.invalidateQueries({ queryKey: ['library'] });
        navigate(`/v/${videoId}`, { replace: true });
      })
      .catch(() => setFailed(true));
  }, [signedIn, videoId, navigate, queryClient, attempt]);

  if (!signedIn && videoId) return <Navigate to={`/login?next=${encodeURIComponent(`/share?url=${videoId}`)}`} replace />;
  return (
    <>
      <PageTitle title="Save to VidWiz" />
      {!videoId ? <EmptyState title="Nothing to save">Share a YouTube video to save it to your library.</EmptyState>
        : failed ? <ErrorState title="The video was not saved" message="Check your connection and try again." onRetry={() => { setFailed(false); setAttempt(value => value + 1); }} />
          : <div className="flex justify-center py-16"><Spinner label="Saving video" /></div>}
    </>
  );
}
