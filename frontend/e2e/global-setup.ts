import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { API_ENV, BACKEND_DIR } from './env'

/** Before the tests: create their database if it's missing, then migrate it. Playwright has
 * started the API by now, but the API only connects to the database when a request comes in */
export default function globalSetup() {
  const options = {
    cwd: BACKEND_DIR,
    env: { ...process.env, ...API_ENV },
    stdio: 'inherit' as const,
  }
  const createDatabase = fileURLToPath(new URL('./create_database.py', import.meta.url))
  execFileSync('uv', ['run', 'python', createDatabase], options)
  execFileSync('uv', ['run', 'alembic', 'upgrade', 'head'], options)
}
