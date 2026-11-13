// Where the end-to-end tests run their own API and app: apart from `make dev` (port 8000) and
// `make fe-dev` (port 5173), and with a database of their own
import { fileURLToPath } from 'node:url'

export const API_PORT = 8001
export const WEB_PORT = 5174
export const API_URL = `http://localhost:${String(API_PORT)}`
export const WEB_URL = `http://localhost:${String(WEB_PORT)}`
export const BACKEND_DIR = fileURLToPath(new URL('../../backend', import.meta.url))

/** The API's settings for the tests: its own database (the tests commit data, while pytest's
 * database relies on rolling back), the app's origin for the Origin check, and cookies over
 * plain HTTP. Set E2E_DATABASE_URL if your Postgres isn't the one `make db-up` starts */
export const API_ENV = {
  DATABASE_URL:
    process.env.E2E_DATABASE_URL ??
    'postgresql+psycopg://postgres:postgres@localhost:5432/strength_journal_e2e',
  ALLOWED_ORIGIN: WEB_URL,
  COOKIE_SECURE: 'false',
}
