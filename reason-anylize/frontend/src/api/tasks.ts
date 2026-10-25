import type { TaskInfo } from '../types/api';
import type { ServerWsEvent } from '../types/ws';
import { api } from './client';

export const taskApi = {
  async get(taskId: number): Promise<TaskInfo> {
    const { data } = await api.get<TaskInfo>(`/api/tasks/${taskId}`);
    return data;
  },

  async events(taskId: number): Promise<ServerWsEvent[]> {
    const { data } = await api.get<{ events: ServerWsEvent[] }>(`/api/tasks/${taskId}/events`);
    return data.events;
  },

  async cancel(taskId: number): Promise<{ task_id: number; requested: boolean; message?: string }> {
    const { data } = await api.post<{ task_id: number; requested: boolean; message?: string }>(
      `/api/tasks/${taskId}/cancel`,
    );
    return data;
  },
};
