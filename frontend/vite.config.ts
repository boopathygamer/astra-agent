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
      port: 3000,
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        // Use bypass to avoid intercepting browser navigation to /chat (React Router route)
        '/chat': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          bypass: (req) => {
            // Only proxy API calls; let browser GET navigations fall through to the SPA
            if (req.method === 'GET' && req.headers.accept?.includes('text/html')) {
              return '/index.html';
            }
          },
        },
        // Use specific sub-paths to avoid colliding with /agent and /tutor React Router routes
        '/agent/task': { target: 'http://localhost:8000', changeOrigin: true },
        '/agent/stats': { target: 'http://localhost:8000', changeOrigin: true },
        '/tutor/start': { target: 'http://localhost:8000', changeOrigin: true },
        '/tutor/respond': { target: 'http://localhost:8000', changeOrigin: true },
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
