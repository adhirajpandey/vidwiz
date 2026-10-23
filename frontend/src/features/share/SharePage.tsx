import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { libraryApi } from '../../api';
import { useSignedIn } from '../../hooks/useSignedIn';
import PageTitle from '../../components/PageTitle';
import EmptyState from '../../components/ui/EmptyState';
import Spinner from '../../components/ui/Spinner';
import { sharedVideoId } from './sharedVideoId';

/** PWA share target: sharing a YouTube video to VidWiz saves and opens it. */
export default function SharePage() {
  const [params] = useSearchParams();
  const signedIn = useSignedIn();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [failed, setFailed] = useState(false);
  const started = useRef(false);
  const videoId = sharedVideoId(params);

  useEffect(() => {
    if (!signedIn || !videoId || started.current) return;
    started.current = true;
    libraryApi.save(videoId)
      .then(() => {
        void queryClient.invalidateQueries({ queryKey: ['library'] });
        navigate(`/v/${videoId}`, { replace: true });
      })
      .catch(() => setFailed(true));
  }, [signedIn, videoId, navigate, queryClient]);

  if (!signedIn && videoId) return <Navigate to={`/login?next=${encodeURIComponent(`/share?url=${videoId}`)}`} replace />;
  return (
    <>
      <PageTitle title="Save to VidWiz" />
      {!videoId ? <EmptyState title="Nothing to save">Share a YouTube video to save it to your library.</EmptyState>
        : failed ? <EmptyState title="The video was not saved">Check your connection and share it again.</EmptyState>
          : <div className="flex justify-center py-16"><Spinner label="Saving video" /></div>}
    </>
  );
}
