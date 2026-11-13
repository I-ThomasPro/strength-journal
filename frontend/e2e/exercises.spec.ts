import { expect, logIn, test } from './fixtures'

test('opening the exercises from the Routines tab, with a tab and search that a reload keeps', async ({
  page,
  admin,
}) => {
  await logIn(page, admin)
  const nav = page.getByRole('navigation', { name: 'Main' })
  await nav.getByRole('link', { name: 'Routines' }).click()
  await page.getByRole('link', { name: 'Exercises' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Exercises' })).toBeVisible()
  await expect(page).toHaveURL(/\/exercises$/)
  await expect(nav.getByRole('link', { name: 'Routines' })).toHaveAttribute('aria-current', 'page')

  // A new account has no exercises of its own yet
  await page.getByRole('tab', { name: 'Mine' }).click()
  await expect(page.getByText('You haven’t added any exercises yet')).toBeVisible()
  await expect(page).toHaveURL(/\/exercises\?scope=mine$/)

  const search = page.getByRole('searchbox', { name: 'Search exercises' })
  await search.fill('squat')
  await expect(page.getByText('No exercises match “squat”')).toBeVisible()

  await page.reload()
  await expect(search).toHaveValue('squat')
  await expect(page.getByRole('tab', { name: 'Mine' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('No exercises match “squat”')).toBeVisible()
})
