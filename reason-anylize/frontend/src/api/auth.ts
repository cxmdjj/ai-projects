import type { User } from '../types/api';
import { api } from './client';

export const authApi = {
  async me(): Promise<User> {
    const { data } = await api.get<User>('/api/auth/me');
    return data;
  },

  async logout(): Promise<void> {
    await api.post('/api/auth/logout');
  },
};
