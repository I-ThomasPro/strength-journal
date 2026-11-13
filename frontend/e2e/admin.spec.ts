import { expect, logIn, PASSWORD, test, uniqueUsername } from './fixtures'

test('an admin creates an account, which logs in without the Admin tab', async ({
  page,
  admin,
}) => {
  await logIn(page, admin)
  const nav = page.getByRole('navigation', { name: 'Main' })
  await nav.getByRole('link', { name: 'Admin' }).click()

  const lifter = {
    username: uniqueUsername('lifter'),
    displayName: 'New Lifter',
    password: PASSWORD,
  }
  await page.getByLabel('Username').fill(lifter.username)
  await page.getByLabel('Display name').fill(lifter.displayName)
  await page.getByLabel('Password').fill(lifter.password)
  await page.getByLabel('Weight unit').selectOption('lb')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('status')).toHaveText(
    `Created @${lifter.username}. They can log in now.`,
  )

  await nav.getByRole('link', { name: 'Profile' }).click()
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Log in' })).toBeVisible()

  await logIn(page, lifter)
  await expect(nav.getByRole('link')).toHaveText(['Train', 'Routines', 'History', 'Profile'])
  await page.goto('/admin')
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
})
