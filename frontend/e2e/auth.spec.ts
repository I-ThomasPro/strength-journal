import { expect, test } from './fixtures'

const TABS = ['Train', 'Routines', 'History', 'Profile', 'Admin']

test('logging in, visiting each tab, and logging out', async ({ page, admin }) => {
  // A signed-in page sends a logged-out visitor to log in, then back
  await page.goto('/history')
  await expect(page).toHaveURL(/\/login\?next=%2Fhistory$/)
  await page.getByLabel('Username').fill(admin.username)
  await page.getByLabel('Password').fill(admin.password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'History' })).toBeVisible()
  await expect(page).toHaveURL(/\/history$/)

  const nav = page.getByRole('navigation', { name: 'Main' })
  for (const tab of TABS) {
    await nav.getByRole('link', { name: tab }).click()
    await expect(page.getByRole('heading', { level: 1, name: tab })).toBeVisible()
    await expect(page).toHaveTitle(`${tab} · Strength Journal`)
  }

  await nav.getByRole('link', { name: 'Profile' }).click()
  await expect(page.getByText(`@${admin.username}`)).toBeVisible()
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Log in' })).toBeVisible()

  // The session ended on the server too, so going back can't show a signed-in page
  await page.goBack()
  await expect(page.getByRole('heading', { level: 1, name: 'Log in' })).toBeVisible()
  expect((await page.request.get('/api/session')).status()).toBe(401)
})
