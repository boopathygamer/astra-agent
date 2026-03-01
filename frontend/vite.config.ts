import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react(), tailwindcss()],
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        '/chat': { target: 'http://localhost:8000', changeOrigin: true },
        '/agent': { target: 'http://localhost:8000', changeOrigin: true },
        '/tutor': { target: 'http://localhost:8000', changeOrigin: true },
        '/swarm': { target: 'http://localhost:8000', changeOrigin: true },
        '/health': { target: 'http://localhost:8000', changeOrigin: true },
        '/memory': { target: 'http://localhost:8000', changeOrigin: true },
        '/sessions': { target: 'http://localhost:8000', changeOrigin: true },
        '/processes': { target: 'http://localhost:8000', changeOrigin: true },
        '/forge': { target: 'http://localhost:8000', changeOrigin: true },
        '/analyze': { target: 'http://localhost:8000', changeOrigin: true },
        '/device': { target: 'http://localhost:8000', changeOrigin: true },
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
        '/ws': { target: 'ws://localhost:8000', ws: true },
      },
    },
  };
});
