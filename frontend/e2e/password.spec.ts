import { expect, logIn, test } from './fixtures'

const NEW_PASSWORD = 'a brand new long password'

test('changing the password, after which only the new one logs in', async ({ page, admin }) => {
  await logIn(page, admin)
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Profile' })
    .click()

  await page.getByLabel('Current password').fill(admin.password)
  // Exact, because "Confirm new password" contains it
  await page.getByLabel('New password', { exact: true }).fill(NEW_PASSWORD)
  await page.getByLabel('Confirm new password').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page.getByRole('status')).toHaveText(
    'Password changed. Your other devices were logged out.',
  )

  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Log in' })).toBeVisible()

  // The old password no longer works
  await page.getByLabel('Username').fill(admin.username)
  await page.getByLabel('Password').fill(admin.password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Wrong username or password')

  await logIn(page, { ...admin, password: NEW_PASSWORD })
})
