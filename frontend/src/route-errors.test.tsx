// What happens when a page or a layout fails to render. The modules below are replaced with
// ones that throw, so this file has its own tests
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { beforeEach, expect, it, vi } from 'vitest'

import { reloadPage } from '@/lib/reload'
import { routes } from '@/routes'

vi.mock('@/lib/reload', () => ({ reloadPage: vi.fn() }))
vi.mock('@/pages/placeholder-page', () => ({
  PlaceholderPage: () => {
    throw new Error('The page broke')
  },
}))
vi.mock('@/components/public-layout', () => ({
  PublicLayout: () => {
    throw new Error('The layout broke')
  },
}))

beforeEach(() => {
  // React and React Router log the errors they catch
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
})

function renderAt(path: string) {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)
}

it('shows the error inside the layout when a page fails, with a way to reload', async () => {
  renderAt('/history')

  const alert = await screen.findByRole('alert')
  expect(within(alert).getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
  // The header and the tab bar are still there
  expect(screen.getByRole('heading', { level: 1, name: 'History' })).toBeInTheDocument()
  expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()

  await userEvent.click(within(alert).getByRole('button', { name: 'Reload' }))
  expect(reloadPage).toHaveBeenCalledOnce()
})

it('shows the error on its own when a layout fails', async () => {
  renderAt('/login')

  const alert = await screen.findByRole('alert')
  expect(within(alert).getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
  expect(within(alert).getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
})
