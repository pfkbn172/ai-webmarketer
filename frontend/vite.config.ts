import path from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// /marketer/ サブパス配置(implementation_plan 7 章)
// SPA は /marketer/ 配下に配信され、API は同オリジンの /marketer/api/v1/ にプロキシされる
export default defineConfig({
  base: '/marketer/',
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/marketer/api': {
        target: 'http://127.0.0.1:3009',
        changeOrigin: false,
        rewrite: (p) => p.replace(/^\/marketer/, ''),
      },
    },
  },
});
