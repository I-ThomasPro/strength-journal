import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { describe, expect, it } from 'vitest'

import { tabs } from '@/navigation'
import { routes } from '@/routes'

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

describe('routes', () => {
  it('sends the root to the Train tab', async () => {
    const router = renderAt('/')

    expect(await screen.findByRole('heading', { name: 'Train' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/train')
  })

  it.each(tabs)('shows the $label tab, marked as current', async ({ path, label }) => {
    renderAt(path)

    expect(await screen.findByRole('heading', { name: label })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { current: 'page' })).toHaveTextContent(label)
  })

  it('switches tabs from the tab bar', async () => {
    const router = renderAt('/train')

    await userEvent.click(await screen.findByRole('link', { name: 'History' }))

    expect(await screen.findByRole('heading', { name: 'History' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/history')
  })

  it('shows a not-found page, with a way back, for unknown addresses', async () => {
    const router = renderAt('/nowhere')

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Go to Train' }))
    expect(router.state.location.pathname).toBe('/train')
  })
})
