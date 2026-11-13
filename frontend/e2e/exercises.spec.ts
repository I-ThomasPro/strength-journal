import { expect, logIn, test } from './fixtures'

test('opening the exercises from the Routines tab', async ({ page, admin }) => {
  await logIn(page, admin)
  const nav = page.getByRole('navigation', { name: 'Main' })
  await nav.getByRole('link', { name: 'Routines' }).click()
  await page.getByRole('link', { name: 'Exercises' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Exercises' })).toBeVisible()
  await expect(page).toHaveURL(/\/exercises$/)
  await expect(nav.getByRole('link', { name: 'Routines' })).toHaveAttribute('aria-current', 'page')

  // The library is empty until it's seeded, and a new account has no exercises of its own
  await expect(page.getByText('No exercises yet')).toBeVisible()
})
