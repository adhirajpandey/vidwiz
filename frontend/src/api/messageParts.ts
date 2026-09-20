export type TextPart = { type: 'text'; text: string };
export type Passage = { chunk_ids: string[]; start_seconds: number; end_seconds: number };
export type BlockCitation = { list_item_index: number | null; passages: Passage[] };
export type BlockPart = { type: 'block'; text: string; citations: BlockCitation[] };
export type CitationPart = {
  type: 'citation';
  chunk_id: string;
  start_seconds: number;
  end_seconds: number;
};
export type MessagePart = TextPart | CitationPart | BlockPart;
export type WizStreamEvent = MessagePart
  | { type: 'done'; message_id: number }
  | { type: 'error'; message: string };

export function parseWizEvent(value: unknown): WizStreamEvent {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('Invalid stream event');
  }
  const data = value as Record<string, unknown>;
  switch (data.type) {
    case 'block':
      if (typeof data.text === 'string' && Array.isArray(data.citations) && data.citations.every(validCitation)) {
        return { type: 'block', text: data.text, citations: data.citations };
      }
      break;
    case 'text':
      if (typeof data.text === 'string') return { type: 'text', text: data.text };
      break;
    case 'citation':
      if (typeof data.chunk_id === 'string' && data.chunk_id.length > 0 &&
          typeof data.start_seconds === 'number' && Number.isFinite(data.start_seconds) && data.start_seconds >= 0 &&
          typeof data.end_seconds === 'number' && Number.isFinite(data.end_seconds) && data.end_seconds >= data.start_seconds) {
        return { type: 'citation', chunk_id: data.chunk_id, start_seconds: data.start_seconds, end_seconds: data.end_seconds };
      }
      break;
    case 'done':
      if (typeof data.message_id === 'number' && Number.isSafeInteger(data.message_id) && data.message_id > 0) {
        return { type: 'done', message_id: data.message_id };
      }
      break;
    case 'error':
      if (typeof data.message === 'string' && data.message.length > 0) return { type: 'error', message: data.message };
  }
  throw new Error('Invalid stream event');
}

function validCitation(value: unknown): value is BlockCitation {
  if (!value || typeof value !== 'object') return false;
  const c = value as BlockCitation;
  return (c.list_item_index === null || (Number.isSafeInteger(c.list_item_index) && c.list_item_index >= 0)) &&
    Array.isArray(c.passages) && c.passages.length > 0 && c.passages.every(p =>
      p && Array.isArray(p.chunk_ids) && p.chunk_ids.length > 0 && p.chunk_ids.every(id => typeof id === 'string' && id.length > 0) &&
      typeof p.start_seconds === 'number' && Number.isFinite(p.start_seconds) && p.start_seconds >= 0 &&
      typeof p.end_seconds === 'number' && Number.isFinite(p.end_seconds) && p.end_seconds >= p.start_seconds);
}
