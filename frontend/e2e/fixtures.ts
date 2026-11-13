// Fixtures and helpers for the end-to-end tests. Import `test` and `expect` from here
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'

import { test as base, expect, type Page } from '@playwright/test'

import { API_ENV, BACKEND_DIR } from './env'

export const PASSWORD = 'a long enough password'

export interface Account {
  username: string
  displayName: string
  password: string
}

/** A username no other test uses, so tests can run at the same time */
export function uniqueUsername(prefix: string): string {
  return `${prefix}-${randomUUID().slice(0, 8)}`
}

/** Creates an admin the way the first one is made: `python -m app.cli create-admin` */
export function createAdmin(): Account {
  const account = {
    username: uniqueUsername('admin'),
    displayName: 'Test Admin',
    password: PASSWORD,
  }
  execFileSync(
    'uv',
    [
      'run',
      'python',
      '-m',
      'app.cli',
      'create-admin',
      '--username',
      account.username,
      '--display-name',
      account.displayName,
      '--password-stdin',
    ],
    { cwd: BACKEND_DIR, env: { ...process.env, ...API_ENV }, input: `${PASSWORD}\n` },
  )
  return account
}

/** Logs in through the login page, ending on Train */
export async function logIn(page: Page, account: Account): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Username').fill(account.username)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Train' })).toBeVisible()
}

export const test = base.extend<{ admin: Account }>({
  /** A fresh admin for each test. (The second argument is Playwright's `use`, renamed so
   * React's hooks lint rule doesn't take it for React's `use`) */
  // eslint-disable-next-line no-empty-pattern -- Playwright fixtures list what they need first
  admin: async ({}, provide) => {
    await provide(createAdmin())
  },
})

export { expect }
