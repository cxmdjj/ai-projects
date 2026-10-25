import { create } from 'zustand';
import type { ChatMessageRecord } from '../types/api';
import type { UIAttachment, UIMessage } from '../types/chat';

interface ChatState {
  conversationId: number | null;
  messages: UIMessage[];
  loadingHistory: boolean;
  sending: boolean;
  lockError: string | null;
  activeTaskId: number | null;
  streamingMessageKey: string | null;

  beginLoadHistory: (conversationId: number) => void;
  loadHistory: (conversationId: number, records: ChatMessageRecord[]) => void;
  setLoadingHistory: (loading: boolean) => void;
  appendUserMessage: (content: string, attachments?: UIAttachment[]) => void;
  startRound: (taskId: number) => void;
  appendDelta: (taskId: number, text: string) => void;
  addTool: (taskId: number, toolName: string) => void;
  finishTool: (taskId: number, toolName: string, summary: string) => void;
  finishRound: (taskId: number) => void;
  resetRound: (taskId: number) => void;
  replaceMessages: (records: ChatMessageRecord[], conversationId: number) => void;
  setSending: (sending: boolean) => void;
  setLockError: (message: string | null) => void;
  clear: () => void;
}

let localSeq = 0;
let toolSeq = 0;

function nextKey(prefix: string): string {
  localSeq += 1;
  return `${prefix}-${Date.now()}-${localSeq}`;
}

function mapHistory(records: ChatMessageRecord[]): UIMessage[] {
  return records.map((record) => {
    if (record.role === 'tool') {
      return {
        key: `history-tool-${record.message_id}`,
        role: 'tool' as const,
        content: record.content,
        createdAt: record.created_at,
        toolName: record.tool_name ?? undefined,
        toolStatus: record.tool_status ?? 'success',
        toolSummary: record.content,
      };
    }
    return {
      key: `history-${record.message_id}`,
      role: record.role === 'assistant' ? ('assistant' as const) : ('user' as const),
      content: record.content,
      createdAt: record.created_at,
      attachments: record.attachments?.map((item) => ({
        attachment_id: item.attachment_id,
        file_name: item.file_name,
        file_type: item.file_type,
        file_size: item.file_size,
        parse_status: item.parse_status,
      })),
    };
  });
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversationId: null,
  messages: [],
  loadingHistory: false,
  sending: false,
  lockError: null,
  activeTaskId: null,
  streamingMessageKey: null,

  beginLoadHistory: (conversationId) =>
    set({
      conversationId,
      messages: [],
      loadingHistory: true,
      sending: false,
      lockError: null,
      activeTaskId: null,
      streamingMessageKey: null,
    }),

  loadHistory: (conversationId, records) => {
    if (get().conversationId !== conversationId) return;
    set({
      messages: mapHistory(records),
      loadingHistory: false,
      activeTaskId: null,
      streamingMessageKey: null,
      sending: false,
    });
  },

  replaceMessages: (records, conversationId) => {
    if (get().conversationId !== conversationId) return;
    set((state) => ({
      messages: mapHistory(records),
      loadingHistory: false,
      streamingMessageKey: null,
      activeTaskId: state.activeTaskId,
    }));
  },

  setLoadingHistory: (loading) => set({ loadingHistory: loading }),

  appendUserMessage: (content, attachments = []) => {
    const message: UIMessage = {
      key: nextKey('user'),
      role: 'user',
      content,
      attachments,
      createdAt: new Date().toISOString(),
      local: true,
    };
    set((state) => ({
      messages: [...state.messages, message],
      sending: true,
      lockError: null,
    }));
  },

  startRound: (taskId) => {
    const state = get();
    if (state.activeTaskId === taskId && state.streamingMessageKey) {
      set({ sending: false, lockError: null });
      return;
    }
    const key = nextKey(`assistant-${taskId}`);
    const placeholder: UIMessage = {
      key,
      role: 'assistant',
      content: '',
      taskId,
      streaming: true,
      createdAt: new Date().toISOString(),
    };
    set((current) => ({
      messages: [...current.messages, placeholder],
      activeTaskId: taskId,
      streamingMessageKey: key,
      sending: false,
      lockError: null,
    }));
  },

  appendDelta: (taskId, text) => {
    if (!text) return;
    set((state) => {
      if (state.activeTaskId !== null && state.activeTaskId !== taskId) {
        return state;
      }
      let key = state.streamingMessageKey;
      let messages = state.messages;
      const streamingExists = key
        ? messages.some((message) => message.key === key && message.role === 'assistant')
        : false;

      if (!key || !streamingExists) {
        key = nextKey(`assistant-${taskId}`);
        messages = [
          ...messages,
          {
            key,
            role: 'assistant',
            content: '',
            taskId,
            streaming: true,
            createdAt: new Date().toISOString(),
          },
        ];
      }

      messages = messages.map((message) =>
        message.key === key
          ? { ...message, content: `${message.content}${text}`, streaming: true }
          : message,
      );
      return {
        ...state,
        messages,
        activeTaskId: taskId,
        streamingMessageKey: key,
      };
    });
  },

  addTool: (taskId, toolName) => {
    set((state) => {
      if (state.activeTaskId !== null && state.activeTaskId !== taskId) return state;
      const activeKey = state.streamingMessageKey;
      let messages = state.messages.map((message) =>
        message.key === activeKey ? { ...message, streaming: false } : message,
      );
      // 若本轮助手占位尚未产出文本，则在工具卡片出现前移除空占位。
      messages = messages.filter(
        (message) => !(message.key === activeKey && message.role === 'assistant' && !message.content),
      );
      toolSeq += 1;
      const toolMessage: UIMessage = {
        key: `tool-${taskId}-${Date.now()}-${toolSeq}`,
        role: 'tool',
        content: '',
        taskId,
        toolName,
        toolStatus: 'running',
        createdAt: new Date().toISOString(),
      };
      return {
        ...state,
        messages: [...messages, toolMessage],
        activeTaskId: taskId,
        streamingMessageKey: null,
      };
    });
  },

  finishTool: (taskId, toolName, summary) => {
    set((state) => {
      if (state.activeTaskId !== null && state.activeTaskId !== taskId) return state;
      let matched = false;
      const messages = [...state.messages];
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        if (
          message.role === 'tool' &&
          message.taskId === taskId &&
          message.toolName === toolName &&
          message.toolStatus === 'running'
        ) {
          messages[i] = {
            ...message,
            toolStatus: 'success',
            toolSummary: summary,
            content: summary,
          };
          matched = true;
          break;
        }
      }
      if (!matched) {
        toolSeq += 1;
        messages.push({
          key: `tool-${taskId}-${Date.now()}-${toolSeq}`,
          role: 'tool',
          content: summary,
          taskId,
          toolName,
          toolStatus: 'success',
          toolSummary: summary,
          createdAt: new Date().toISOString(),
        });
      }
      return { ...state, messages };
    });
  },

  finishRound: (taskId) => {
    set((state) => {
      const activeKey = state.streamingMessageKey;
      const messages = state.messages
        .map((message) =>
          message.taskId === taskId && message.role === 'assistant'
            ? { ...message, streaming: false }
            : message,
        )
        .filter(
          (message) =>
            !(message.taskId === taskId && message.role === 'assistant' && !message.content),
        );
      return {
        ...state,
        messages,
        streamingMessageKey: activeKey && messages.some((message) => message.key === activeKey)
          ? activeKey
          : null,
      };
    });
  },

  resetRound: (taskId) => {
    set((state) => ({
      ...state,
      messages: state.messages.filter(
        (message) => !(message.taskId === taskId && message.role !== 'user'),
      ),
      streamingMessageKey: null,
      activeTaskId: state.activeTaskId === taskId ? null : state.activeTaskId,
    }));
  },

  setSending: (sending) => set({ sending }),

  setLockError: (message) => set({ lockError: message, sending: false }),

  clear: () =>
    set({
      conversationId: null,
      messages: [],
      loadingHistory: false,
      sending: false,
      lockError: null,
      activeTaskId: null,
      streamingMessageKey: null,
    }),
}));
