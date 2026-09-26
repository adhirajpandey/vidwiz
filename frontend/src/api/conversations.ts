import config from '../config';
import { apiRequest } from './fetch';
import type {
  ConversationCreate,
  ConversationRead,
  MessageRead,
} from './types';

export const conversationsApi = {
  createConversation: (body: ConversationCreate) =>
    apiRequest<ConversationRead>('POST', '/conversations', { body }),
  getConversation: (conversationId: number) =>
    apiRequest<ConversationRead>('GET', `/conversations/${conversationId}`),
  listMessages: (conversationId: number) =>
    apiRequest<MessageRead[]>('GET', `/conversations/${conversationId}/messages`),
  // Streaming responses are read with apiFetch directly.
  getSendMessageUrl: (conversationId: number) =>
    `${config.API_URL}/conversations/${conversationId}/messages`,
};
