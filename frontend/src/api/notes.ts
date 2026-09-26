import apiClient from './client';
import type {
  MessageResponse,
  NoteRead,
  NoteSearchResponse,
  NoteUpdate,
} from './types';

export const notesApi = {
  search: async (q: string, page: number) => (await apiClient.get<NoteSearchResponse>('/notes/search', { params: { q, page, per_page: 10 } })).data,
  listNotes: async (videoId: string) => {
    const response = await apiClient.get<NoteRead[]>(`/videos/${videoId}/notes`);
    return response.data;
  },

  updateNote: async (noteId: number, payload: NoteUpdate) => {
    const response = await apiClient.patch<NoteRead>(
      `/notes/${noteId}`,
      payload
    );
    return response.data;
  },

  deleteNote: async (noteId: number) => {
    const response = await apiClient.delete<MessageResponse>(`/notes/${noteId}`);
    return response.data;
  },
};
