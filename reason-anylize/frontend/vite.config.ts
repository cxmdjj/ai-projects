import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// API 与认证请求统一走相对路径，由 Vite 代理到后端，保证 Cookie 同源。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
        ws: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: false,
        // 后端完成 OAuth 换票后会 302 到前端 /auth/callback。
        // 该路径不含 code/state 时应交给 SPA 路由处理，其余 /auth/* 仍代理到后端。
        bypass(req) {
          if (!req.url) return undefined;
          const url = new URL(req.url, 'http://localhost');
          if (url.pathname === '/auth/callback' && !url.searchParams.has('code')) {
            return '/index.html';
          }
          return undefined;
        },
      },
    },
  },
});
