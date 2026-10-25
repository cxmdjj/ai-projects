import { create } from 'zustand';
import { getErrorMessage } from '../api/client';
import { resultApi } from '../api/results';
import type { AnalysisResult } from '../types/api';

interface ResultState {
  taskId: number | null;
  result: AnalysisResult | null;
  loading: boolean;
  error: string | null;
  fetchResult: (taskId: number) => Promise<void>;
  reset: () => void;
}

export const useResultStore = create<ResultState>((set, get) => ({
  taskId: null,
  result: null,
  loading: false,
  error: null,

  fetchResult: async (taskId) => {
    set({ taskId, loading: true, error: null, result: null });
    try {
      const result = await resultApi.get(taskId);
      if (get().taskId !== taskId) return;
      set({ result, loading: false });
    } catch (error) {
      if (get().taskId !== taskId) return;
      set({
        loading: false,
        result: null,
        error: getErrorMessage(error, '分析结果加载失败'),
      });
    }
  },

  reset: () => set({ taskId: null, result: null, loading: false, error: null }),
}));
