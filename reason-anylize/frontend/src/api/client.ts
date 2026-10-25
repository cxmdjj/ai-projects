import axios from 'axios';

/**
 * 全站使用相对路径请求，生产由同域反向代理承接，开发由 Vite proxy 转发。
 * Cookie 是 HttpOnly 的 session_token，因此必须开启 withCredentials。
 */
export const api = axios.create({
  baseURL: '',
  withCredentials: true,
  timeout: 90_000,
  headers: {
    Accept: 'application/json',
  },
});

let redirectingToLogin = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const path = window.location.pathname;
      const isAuthPage = path.startsWith('/login') || path.startsWith('/auth/callback');
      if (!isAuthPage && !redirectingToLogin) {
        redirectingToLogin = true;
        window.location.assign('/login');
      }
    }
    return Promise.reject(error);
  },
);

export function getErrorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (error.code === 'ECONNABORTED') {
      return '请求超时，请稍后重试';
    }
    if (!error.response) {
      return '无法连接到服务，请确认后端已启动';
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
