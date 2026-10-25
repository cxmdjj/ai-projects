import type { AttachmentMeta, AttachmentUploadResponse } from '../types/api';
import { api } from './client';

export const attachmentApi = {
  async list(conversationId: number): Promise<AttachmentMeta[]> {
    const { data } = await api.get<{ attachments: AttachmentMeta[] }>('/api/attachment/ls', {
      params: { conversation_id: conversationId },
    });
    return data.attachments;
  },

  async upload(
    conversationId: number,
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<AttachmentUploadResponse> {
    const form = new FormData();
    form.append('conversation_id', String(conversationId));
    form.append('file', file);
    const { data } = await api.post<AttachmentUploadResponse>('/api/attachment/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000,
      onUploadProgress: (event) => {
        if (!onProgress) return;
        const total = event.total ?? file.size;
        if (total > 0) {
          onProgress(Math.min(100, Math.round((event.loaded / total) * 100)));
        }
      },
    });
    return data;
  },

  async delete(attachmentId: number): Promise<void> {
    await api.post('/api/attachment/delete', { attachment_id: attachmentId });
  },

  downloadUrl(attachmentId: number): string {
    return `/api/attachment/get?attachment_id=${encodeURIComponent(String(attachmentId))}`;
  },
};
