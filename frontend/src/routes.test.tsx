import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { tabs } from '@/navigation'
import { renderApp } from '@/test/render'
import { loggedInAs } from '@/test/session'

function renderAt(path: string) {
  return renderApp(path, loggedInAs()).router
}

describe('routes', () => {
  it('sends the root to the Train tab', async () => {
    const router = renderAt('/')

    expect(await screen.findByRole('heading', { level: 1, name: 'Train' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/train')
  })

  it.each(tabs)('titles the $label tab and marks it as current', async ({ path, label }) => {
    renderAt(path)

    expect(await screen.findByRole('heading', { level: 1, name: label })).toBeInTheDocument()
    expect(document.title).toBe(`${label} · Strength Journal`)
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link')).toHaveLength(tabs.length)
    expect(within(nav).getByRole('link', { current: 'page' })).toHaveTextContent(label)
  })

  it('switches tabs from the tab bar', async () => {
    const router = renderAt('/train')

    await userEvent.click(await screen.findByRole('link', { name: 'History' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'History' })).toBeInTheDocument()
    expect(document.title).toBe('History · Strength Journal')
    expect(router.state.location.pathname).toBe('/history')
  })

  it('shows the login page in the signed-out layout, without the tab bar', async () => {
    renderApp('/login') // logged out

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(screen.getByText('Strength Journal')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(document.title).toBe('Log in · Strength Journal')
  })

  it('shows a not-found page, with a way back, for unknown addresses', async () => {
    const router = renderAt('/nowhere')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }),
    ).toBeInTheDocument()
    expect(document.title).toBe('Page not found · Strength Journal')
    await userEvent.click(screen.getByRole('link', { name: 'Go to Train' }))
    expect(router.state.location.pathname).toBe('/train')
  })
})
