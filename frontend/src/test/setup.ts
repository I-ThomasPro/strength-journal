// Runs before each test file (vite.config.ts `test.setupFiles`)
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Testing Library only unmounts on its own when the test runner has globals, which Vitest
// leaves off
afterEach(() => {
  cleanup()
})
