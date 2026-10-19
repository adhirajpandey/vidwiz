import type { WizMessage } from '../../hooks/useWizChat';

/** Video ids cited anywhere in the conversation, so citations can show titles. */
export function citedVideoIds(messages: WizMessage[]): string[] {
  const ids = new Set<string>();
  for (const message of messages) {
    for (const part of message.parts) {
      if (part.type !== 'block') continue;
      for (const citation of part.citations) {
        for (const passage of citation.passages) if (passage.video_id) ids.add(passage.video_id);
      }
    }
  }
  return [...ids];
}
