import { create } from 'zustand';
import { chatApi } from '../api/chat';
import type { Conversation } from '../types/api';
import { forgetLatestTask } from '../utils/taskCache';

interface ConversationState {
  conversations: Conversation[];
  activeConversationId: number | null;
  loading: boolean;
  initialized: boolean;
  error: string | null;
  fetchConversations: () => Promise<Conversation[]>;
  createConversation: (title?: string) => Promise<Conversation>;
  renameConversation: (id: number, title: string) => Promise<Conversation>;
  setArchived: (id: number, archived: boolean) => Promise<Conversation>;
  deleteConversation: (id: number) => Promise<number>;
  setActiveConversation: (id: number | null) => void;
  clear: () => void;
  touchConversation: (id: number, at?: string) => void;
}

function sortConversations(items: Conversation[]): Conversation[] {
  return [...items].sort((a, b) => {
    const ta = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
    const tb = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
    if (tb !== ta) return tb - ta;
    return b.conversation_id - a.conversation_id;
  });
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  loading: false,
  initialized: false,
  error: null,

  fetchConversations: async () => {
    set({ loading: true, error: null });
    try {
      const items = await chatApi.listConversations();
      const activeId = get().activeConversationId;
      const activeStillExists =
        activeId !== null && items.some((item) => item.conversation_id === activeId);
      set({
        conversations: sortConversations(items),
        loading: false,
        initialized: true,
        activeConversationId: activeStillExists ? activeId : null,
      });
      return items;
    } catch (error) {
      set({
        loading: false,
        initialized: true,
        error: error instanceof Error ? error.message : '会话列表加载失败',
      });
      throw error;
    }
  },

  createConversation: async (title = '新会话') => {
    const conversation = await chatApi.createConversation(title);
    set((state) => ({
      conversations: sortConversations([conversation, ...state.conversations]),
      activeConversationId: conversation.conversation_id,
    }));
    return conversation;
  },

  renameConversation: async (id, title) => {
    const updated = await chatApi.updateConversation({ conversation_id: id, title });
    set((state) => ({
      conversations: state.conversations.map((item) =>
        item.conversation_id === id ? { ...item, title: updated.title } : item,
      ),
    }));
    return updated;
  },

  setArchived: async (id, archived) => {
    const updated = await chatApi.updateConversation({
      conversation_id: id,
      status: archived ? 'archived' : 'active',
    });
    set((state) => ({
      conversations: state.conversations.map((item) =>
        item.conversation_id === id
          ? { ...item, status: updated.status, title: updated.title }
          : item,
      ),
    }));
    return updated;
  },

  deleteConversation: async (id) => {
    const deleted = await chatApi.deleteConversations([id]);
    forgetLatestTask(id);
    set((state) => ({
      conversations: state.conversations.filter((item) => item.conversation_id !== id),
      activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
    }));
    return deleted;
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  clear: () =>
    set({
      conversations: [],
      activeConversationId: null,
      loading: false,
      initialized: false,
      error: null,
    }),

  touchConversation: (id, at = new Date().toISOString()) =>
    set((state) => ({
      conversations: sortConversations(
        state.conversations.map((item) =>
          item.conversation_id === id ? { ...item, last_message_at: at } : item,
        ),
      ),
    })),
}));
