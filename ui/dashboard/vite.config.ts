import path from 'path'

import react from '@vitejs/plugin-react'
// vitest/config extends vite's UserConfig with the `test` block.
import { defineConfig } from 'vitest/config'

// Backend proxy points at the future services/routing FastAPI service.
// Until that service exists, requests to /api* will fail-fast; the
// dashboard uses mock data in src/lib/api.ts in the meantime.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3091,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8091',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, '')
      }
    }
  },
  preview: {
    port: 3091
  },
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./src/test-setup.ts']
  }
})
