import config from '../config';
import { apiRequest } from './fetch';
import type {
  ConversationCreate,
  ConversationList,
  ConversationRead,
  ConversationScope,
  MessageRead,
} from './types';

export const conversationsApi = {
  createConversation: (body: ConversationCreate) =>
    apiRequest<ConversationRead>('POST', '/conversations', { body }),
  getConversation: (conversationId: number) =>
    apiRequest<ConversationRead>('GET', `/conversations/${conversationId}`),
  list: (params: { scope?: ConversationScope; video_id?: string; page?: number; per_page?: number } = {}) =>
    apiRequest<ConversationList>('GET', '/conversations', { params: { ...params } }),
  listMessages: (conversationId: number) =>
    apiRequest<MessageRead[]>('GET', `/conversations/${conversationId}/messages`),
  // Streaming responses are read with apiFetch directly.
  getSendMessageUrl: (conversationId: number) =>
    `${config.API_URL}/conversations/${conversationId}/messages`,
};
