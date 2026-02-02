import apiClient from './client';
import type {
  ConversationCreate,
  ConversationRead,
  MessageRead,
} from './types';
import config from '../config';

export const conversationsApi = {
  createConversation: async (payload: ConversationCreate) => {
    const response = await apiClient.post<ConversationRead>(
      '/conversations',
      payload
    );
    return response.data;
  },

  getConversation: async (conversationId: number) => {
    const response = await apiClient.get<ConversationRead>(
      `/conversations/${conversationId}`
    );
    return response.data;
  },

  listMessages: async (conversationId: number) => {
    const response = await apiClient.get<MessageRead[]>(
      `/conversations/${conversationId}/messages`
    );
    return response.data;
  },

  // Helper to construct the full URL for fetch/native usage if needed (e.g. streaming)
  // although we can also use fetch with token.
  getSendMessageUrl: (conversationId: number) => {
    return `${config.API_URL}/conversations/${conversationId}/messages`;
  },
};
