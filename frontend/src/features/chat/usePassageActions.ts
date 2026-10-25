import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Passage } from '../../api/messageParts';
import type { PassageActions } from '../../components/wiz/WizCitation';
import { useNotify } from '../../hooks/useNotify';
import { useSavePassage } from '../moments/queries';

/**
 * Citation actions. Within a video, passages seek the on-page player; library
 * passages (with video_id) open their video at that time.
 */
export function usePassageActions({ videoId, seek, signedIn, videoLabel }: {
  videoId?: string;
  seek?: (seconds: number) => void;
  signedIn: boolean;
  videoLabel?: (videoId: string) => string | undefined;
}): PassageActions {
  const navigate = useNavigate();
  const save = useSavePassage();
  const notify = useNotify();
  return useMemo(() => ({
    watchHref: (passage: Passage) => {
      const target = passage.video_id ?? videoId;
      return target && !(seek && (!passage.video_id || passage.video_id === videoId))
        ? `/v/${target}?t=${Math.floor(passage.start_seconds)}` : undefined;
    },
    watch: (passage: Passage) => {
      const target = passage.video_id ?? videoId;
      if (seek && (!passage.video_id || passage.video_id === videoId)) seek(passage.start_seconds);
      else if (target) navigate(`/v/${target}?t=${Math.floor(passage.start_seconds)}`);
    },
    save: signedIn
      ? async (passage: Passage) => {
        const target = passage.video_id ?? videoId;
        if (!target) return;
        try {
          const result = await save.mutateAsync({
            video_id: target, start_seconds: passage.start_seconds, end_seconds: passage.end_seconds,
          });
          notify.success(result.merged ? 'Added to a nearby moment' : 'Saved as a moment');
        } catch (cause) {
          notify.error(cause, 'Passage not saved', 'The passage could not be saved.');
          throw cause;
        }
      }
      : undefined,
    videoLabel,
  }), [videoId, seek, signedIn, videoLabel, navigate, save, notify]);
}
