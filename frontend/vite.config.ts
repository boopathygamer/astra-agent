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
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        // Forward all backend API paths to the FastAPI server
        // Note: /agent and /tutor are also frontend routes, so proxy specific sub-paths
        '/chat': 'http://localhost:8000',
        '/health': 'http://localhost:8000',
        '/providers': 'http://localhost:8000',
        '/agent/task': 'http://localhost:8000',
        '/agent/stats': 'http://localhost:8000',
        '/tutor/start': 'http://localhost:8000',
        '/tutor/respond': 'http://localhost:8000',
        '/swarm': 'http://localhost:8000',
        '/memory': 'http://localhost:8000',
        '/sessions': 'http://localhost:8000',
        '/processes': 'http://localhost:8000',
        '/forge': 'http://localhost:8000',
        '/analyze': 'http://localhost:8000',
        '/device': 'http://localhost:8000',
        '/council': 'http://localhost:8000',
        '/scan': 'http://localhost:8000',
        '/docs': 'http://localhost:8000',
        '/ws': {
          target: 'http://localhost:8000',
          ws: true,
        },
      },
    },
  };
});
