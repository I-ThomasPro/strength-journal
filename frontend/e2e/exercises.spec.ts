import { addExercise, expect, logIn, test } from './fixtures'

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

test('adding an exercise, finding it by searching, and not adding it twice', async ({
  page,
  admin,
}) => {
  await logIn(page, admin)
  await page.goto('/exercises')

  await page.getByRole('button', { name: 'New exercise' }).click()
  await page.getByLabel('Name', { exact: true }).fill('Zercher Squat')
  await page.getByRole('button', { name: 'Add exercise' }).click()
  await expect(page.getByRole('status')).toHaveText('Added “Zercher Squat”')

  // It's one of the user's own, and a search finds it
  await page.getByRole('tab', { name: 'Mine' }).click()
  await page.getByRole('searchbox', { name: 'Search exercises' }).fill('zercher')
  const rows = page.getByRole('tabpanel').getByRole('listitem')
  await expect(rows).toHaveText(['Zercher Squat'])
  await page.reload()
  await expect(rows).toHaveText(['Zercher Squat'])

  // The same name again, in another case, goes on the name field
  await page.getByRole('button', { name: 'New exercise' }).click()
  await page.getByLabel('Name', { exact: true }).fill('zercher squat')
  await page.getByRole('button', { name: 'Add exercise' }).click()
  await expect(page.getByText('You already have an exercise with this name')).toBeVisible()
})

test('opening an exercise from the list, and going back to the same search', async ({
  page,
  admin,
}) => {
  await logIn(page, admin)
  await addExercise(page, 'Zercher Squat')
  await page.goto('/exercises?scope=mine&q=zercher')

  await page.getByRole('link', { name: 'Zercher Squat' }).click()
  await expect(page.getByRole('heading', { level: 2, name: 'Zercher Squat' })).toBeVisible()
  await expect(page.getByText('Your exercise')).toBeVisible()
  await expect(page).toHaveURL(/\/exercises\/[0-9a-f-]{36}$/)
  await expect(
    page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Routines' }),
  ).toHaveAttribute('aria-current', 'page')

  // A reload keeps the way back
  await page.reload()
  await page.getByRole('link', { name: 'Exercises' }).click()
  await expect(page).toHaveURL(/\/exercises\?scope=mine&q=zercher$/)
  await expect(page.getByRole('tabpanel').getByRole('listitem')).toHaveText(['Zercher Squat'])

  // An address that isn't one of this user's exercises
  await page.goto('/exercises/00000000-0000-4000-8000-000000000000')
  await expect(
    page.getByText('This exercise doesn’t exist. It may have been deleted.'),
  ).toBeVisible()
  await page.goto('/exercises/not-an-id')
  await expect(
    page.getByText('This exercise doesn’t exist. It may have been deleted.'),
  ).toBeVisible()
})
