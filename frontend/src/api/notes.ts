import apiClient from './client';
import type {
  MessageResponse,
  NoteCreate,
  NoteRead,
  NoteUpdate,
} from './types';

export const notesApi = {
  listNotes: async (videoId: string) => {
    const response = await apiClient.get<NoteRead[]>(`/videos/${videoId}/notes`);
    return response.data;
  },

  createNote: async (videoId: string, payload: NoteCreate) => {
    const response = await apiClient.post<NoteRead>(
      `/videos/${videoId}/notes`,
      payload
    );
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
