import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // Read VITE_* only. Backend credentials from the root .env stay server-side.
  const env = loadEnv(mode, '..', 'VITE_');
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000';

  return {
    plugins: [react()],
    envDir: '..',
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api(?=\/|$)/, ''),
        },
        '/ws': {
          target,
          changeOrigin: true,
          ws: true,
          rewrite: (path) => path.replace(/^\/ws(?=\/|$)/, ''),
        },
      },
    },
    preview: {
      port: 4173,
      strictPort: true,
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
  };
});
