import { create } from 'zustand';
import { attachmentApi } from '../api/attachment';
import { getErrorMessage } from '../api/client';
import type { AttachmentMeta } from '../types/api';

interface AttachmentState {
  conversationId: number | null;
  attachments: AttachmentMeta[];
  loading: boolean;
  error: string | null;
  fetchAttachments: (conversationId: number) => Promise<void>;
  deleteAttachment: (attachmentId: number) => Promise<void>;
  reset: () => void;
}

let requestSeq = 0;

export const useAttachmentStore = create<AttachmentState>((set, get) => ({
  conversationId: null,
  attachments: [],
  loading: false,
  error: null,

  fetchAttachments: async (conversationId) => {
    requestSeq += 1;
    const seq = requestSeq;
    set({ conversationId, loading: true, error: null });
    try {
      const items = await attachmentApi.list(conversationId);
      if (seq !== requestSeq || get().conversationId !== conversationId) return;
      set({ attachments: items, loading: false });
    } catch (error) {
      if (seq !== requestSeq || get().conversationId !== conversationId) return;
      set({
        loading: false,
        error: getErrorMessage(error, '附件列表加载失败'),
      });
    }
  },

  deleteAttachment: async (attachmentId) => {
    await attachmentApi.delete(attachmentId);
    set((state) => ({
      attachments: state.attachments.filter((item) => item.attachment_id !== attachmentId),
    }));
  },

  reset: () => {
    requestSeq += 1;
    set({ conversationId: null, attachments: [], loading: false, error: null });
  },
}));
