import { apiRequest } from './fetch';
import type {
  MessageResponse,
  NoteRead,
  NoteSearchResponse,
  NoteUpdate,
} from './types';

export const notesApi = {
  search: (q: string, page: number) =>
    apiRequest<NoteSearchResponse>('GET', '/notes/search', {
      params: { q, page, per_page: 10 },
    }),
  listNotes: (videoId: string) =>
    apiRequest<NoteRead[]>('GET', `/videos/${videoId}/notes`),
  updateNote: (noteId: number, body: NoteUpdate) =>
    apiRequest<NoteRead>('PATCH', `/notes/${noteId}`, { body }),
  deleteNote: (noteId: number) =>
    apiRequest<MessageResponse>('DELETE', `/notes/${noteId}`),
};
