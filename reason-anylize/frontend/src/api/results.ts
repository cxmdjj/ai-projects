import type { AnalysisResult } from '../types/api';
import { api } from './client';

export type ExportFormat = 'md' | 'html' | 'json';

export const resultApi = {
  async get(taskId: number): Promise<AnalysisResult> {
    const { data } = await api.get<AnalysisResult>(`/api/results/${taskId}`);
    return data;
  },

  exportUrl(taskId: number, format: ExportFormat): string {
    return `/api/results/${taskId}/export?format=${format}`;
  },

  downloadUrl(taskId: number, file?: string): string {
    const suffix = file ? `?file=${encodeURIComponent(file)}` : '';
    return `/api/results/${taskId}/download${suffix}`;
  },
};
