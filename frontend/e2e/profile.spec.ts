import { expect, logIn, test } from './fixtures'

test('changing the display name and weight unit, which a reload keeps', async ({ page, admin }) => {
  await logIn(page, admin)
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Profile' })
    .click()

  await page.getByLabel('Display name').fill('Renamed Admin')
  await page.getByLabel('Weight unit').selectOption('lb')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByRole('status')).toHaveText('Saved')
  await expect(page.getByRole('region', { name: 'Account' })).toContainText('Renamed Admin')

  await page.reload()
  await expect(page.getByLabel('Display name')).toHaveValue('Renamed Admin')
  await expect(page.getByLabel('Weight unit')).toHaveValue('lb')
  await expect(page.getByRole('region', { name: 'Account' })).toContainText('Renamed Admin')
})
