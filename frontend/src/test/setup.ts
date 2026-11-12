// Runs before each test file (vite.config.ts `test.setupFiles`)
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { setCsrfToken } from '@/api/client'
import { server } from '@/test/server'

beforeAll(() => {
  server.listen({ onUnhandledFrame: 'error' })
})

afterEach(() => {
  // Testing Library only unmounts on its own when the test runner has globals, which Vitest
  // leaves off
  cleanup()
  server.resetHandlers()
  setCsrfToken(null)
})

afterAll(() => {
  server.close()
})
