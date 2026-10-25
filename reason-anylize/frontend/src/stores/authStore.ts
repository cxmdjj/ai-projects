import { create } from 'zustand';
import { authApi } from '../api/auth';
import type { User } from '../types/api';

interface AuthState {
  user: User | null;
  initialized: boolean;
  loading: boolean;
  initialize: () => Promise<void>;
  fetchMe: () => Promise<User | null>;
  setUser: (user: User | null) => void;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  initialized: false,
  loading: false,

  initialize: async () => {
    if (get().initialized) return;
    set({ loading: true });
    try {
      const user = await authApi.me();
      set({ user, initialized: true, loading: false });
    } catch {
      set({ user: null, initialized: true, loading: false });
    }
  },

  fetchMe: async () => {
    set({ loading: true });
    try {
      const user = await authApi.me();
      set({ user, initialized: true, loading: false });
      return user;
    } catch (error) {
      set({ user: null, initialized: true, loading: false });
      throw error;
    }
  },

  setUser: (user) => set({ user, initialized: true }),

  logout: async () => {
    try {
      await authApi.logout();
    } finally {
      set({ user: null });
    }
  },
}));
