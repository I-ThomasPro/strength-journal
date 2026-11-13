import { defineConfig, devices } from '@playwright/test'

import { API_ENV, API_PORT, API_URL, BACKEND_DIR, WEB_PORT, WEB_URL } from './e2e/env'

// End-to-end tests: Playwright starts the API and the app on their own ports (e2e/env.ts), the
// global setup prepares their database, and the tests drive the app in Chromium at phone size
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  expect: { timeout: 10_000 },
  use: {
    baseURL: WEB_URL,
    // Off for speed; re-run a failing test with `pnpm e2e --trace on` to record one
    trace: 'off',
    // A failing test's last screen, for the report (CI uploads it as an artifact)
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'phone',
      use: {
        ...devices['Pixel 7'],
        // To use a Chromium that's already installed instead of `playwright install chromium`
        launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
      },
    },
  ],
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${String(API_PORT)}`,
      cwd: BACKEND_DIR,
      env: API_ENV,
      // Not /api/health: it needs the database, which the global setup creates afterwards
      url: `${API_URL}/api/openapi.json`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'pnpm exec vite',
      env: { PORT: String(WEB_PORT), API_URL },
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
