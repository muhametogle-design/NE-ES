import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Hosts allowed to reach the dev/preview server. Vite blocks unknown Host headers
// by default, which breaks reverse-proxied / tunneled previews ( Codespaces,
// Gitpod, dev containers, Arena live preview, ngrok, ...).
//
//   VITE_ALLOWED_HOSTS="*"                     -> allow any host (dev default)
//   VITE_ALLOWED_HOSTS=".githubpreview.dev,foo" -> allow a suffix + exact names
//   unset                                      -> allow any host in dev
const parseAllowedHosts = (raw) => {
  if (raw === undefined) return true;
  const value = raw.trim();
  if (value === '' || value === '*' || value === 'true') return true;
  return value
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean);
};

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const allowedHosts = parseAllowedHosts(env.VITE_ALLOWED_HOSTS);

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: Number(env.VITE_PORT || 3000),
      strictPort: false,
      allowedHosts,
      // Relative URLs only — never point the browser at localhost:8000, the dev
      // server proxies API + WebSocket traffic to the backend for us.
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: (env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(
            /^http/,
            'ws',
          ),
          ws: true,
        },
      },
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
      allowedHosts,
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      // Keep the SPA reachable when FastAPI serves web/dist from a sub-path.
      sourcemap: command === 'build' ? false : true,
    },
  };
});
