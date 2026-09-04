import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Dev server config tuned for VS Code / Docker / WSL2.
 *
 * ERR_EMPTY_RESPONSE is almost always one of:
 *  - the server bound to 127.0.0.1 inside a container (nothing answers on the host port)
 *  - Vite silently falling back to another port (strictPort: false)
 *  - the HMR websocket advertising an unreachable host, killing the connection
 * All three are pinned down explicitly below.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // Inside docker-compose use the service name; on bare metal use loopback.
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000';
  const wsTarget = apiTarget.replace(/^http/, 'ws');

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',      // listen on every interface, not just loopback
      port: 5173,
      strictPort: true,     // fail loudly instead of silently hopping ports
      open: false,
      cors: true,
      // Accept the VS Code / Codespaces / tunnel hostnames that proxy to us.
      allowedHosts: true,
      hmr: {
        // Browser connects back over the same host it loaded the page from.
        host: env.VITE_HMR_HOST || 'localhost',
        protocol: 'ws',
        clientPort: Number(env.VITE_HMR_CLIENT_PORT || 5173),
      },
      watch: {
        // Required for reliable file events on Docker/WSL bind mounts.
        usePolling: env.VITE_USE_POLLING === 'true',
        interval: 300,
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          xfwd: true,
          timeout: 0,
          proxyTimeout: 0,
        },
        '/ws': {
          target: wsTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          timeout: 0,
          proxyTimeout: 0,
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    preview: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: mode !== 'production',
    },
  };
});
