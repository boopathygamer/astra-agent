import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
        manifest: {
          name: 'Astra Agent Global',
          short_name: 'Astra',
          description: 'Astra Agent Autonomous System',
          theme_color: '#000000',
          background_color: '#000000',
          display: 'standalone',
          icons: [
            {
              src: 'pwa-192x192.png',
              sizes: '192x192',
              type: 'image/png'
            },
            {
              src: 'pwa-512x512.png',
              sizes: '512x512',
              type: 'image/png'
            }
          ]
        },
        workbox: {
          // Cache WebLLM assets aggressively so they work entirely offline
          globPatterns: ['**/*.{js,css,html,ico,png,svg,wasm}'],
          maximumFileSizeToCacheInBytes: 10 * 1024 * 1024, // 10MB to cover web workers
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'google-fonts-cache',
                expiration: {
                  maxEntries: 10,
                  maxAgeSeconds: 60 * 60 * 24 * 365
                },
                cacheableResponse: {
                  statuses: [0, 200]
                }
              }
            }
          ]
        }
      })
    ],
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
      // Do not modify — file watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        // Forward backend API paths to the FastAPI server.
        // /chat collides with the frontend route, so use bypass to let
        // browser page navigations (Accept: text/html) fall through to the SPA.
        '/chat': {
          target: 'http://localhost:8000',
          bypass(req) {
            if (req.headers.accept?.includes('text/html')) return req.url;
          },
        },
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
        '/orchestrate': 'http://localhost:8000',
        '/mcp': 'http://localhost:8000',
        '/docs': 'http://localhost:8000',
        '/asi': 'http://localhost:8000',
        '/dev': 'http://localhost:8000',
        '/airllm': 'http://localhost:8000',
        '/ws': {
          target: 'http://localhost:8000',
          ws: true,
        },
      },
    },
  };
});
