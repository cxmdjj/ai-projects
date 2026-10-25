import type {
  ChatMessageRecord,
  Conversation,
  WsTokenResponse,
} from '../types/api';
import { api } from './client';

export const chatApi = {
  async listConversations(): Promise<Conversation[]> {
    const { data } = await api.get<{ conversations: Conversation[] }>('/api/chat/ls');
    return data.conversations;
  },

  async createConversation(title = '新会话'): Promise<Conversation> {
    const { data } = await api.post<Conversation>('/api/chat/create', { title });
    return data;
  },

  async deleteConversations(conversationIds: number[]): Promise<number> {
    const { data } = await api.post<{ deleted: number }>('/api/chat/delete', {
      conversation_ids: conversationIds,
    });
    return data.deleted;
  },

  async updateConversation(input: {
    conversation_id: number;
    title?: string;
    status?: 'active' | 'archived';
  }): Promise<Conversation> {
    const { data } = await api.post<Conversation>('/api/chat/update', input);
    return data;
  },

  async listMessages(conversationId: number): Promise<ChatMessageRecord[]> {
    const { data } = await api.get<{ messages: ChatMessageRecord[] }>(
      `/api/chat/ls/${conversationId}`,
    );
    return data.messages;
  },

  async getWsToken(): Promise<WsTokenResponse> {
    const { data } = await api.post<WsTokenResponse>('/api/chat/ws-token');
    return data;
  },
};
