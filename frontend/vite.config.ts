/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API (`make dev`) listens on port 8000. Proxying /api keeps the browser on one origin, as
// in production, so the session cookie and the API's Origin check work. The port must match
// the API's ALLOWED_ORIGIN, http://localhost:5173 by default
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'
const server = { port: 5173, strictPort: true, proxy: { '/api': apiUrl } }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server,
  preview: server,
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})
