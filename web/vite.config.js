import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// NE-EMIS — Vite configuration
//   • Dev server binds 0.0.0.0:5173 so the container port is reachable.
//   • /api is proxied to the FastAPI backend on :8000 (default 127.0.0.1;
//     overridden to http://app:8000 inside docker-compose via env var).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // Accept tunnel/preview hosts (Docker Desktop, e2b/sandbox proxies, etc.).
    allowedHosts: true,
    watch: {
      usePolling: true, // required for HMR across bind mounts (Docker/VM)
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
