import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { apiFetch } from '@/api/client'
import { useSession } from '@/auth/session'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs, loggedOut, testUser } from '@/test/session'

function renderUseSession() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => useSession(), { wrapper })
}

describe('useSession', () => {
  it('is loading, then logged out when the API answers 401', async () => {
    server.use(loggedOut())
    const { result } = renderUseSession()

    expect(result.current).toEqual({ status: 'loading', user: null })
    await waitFor(() => {
      expect(result.current).toEqual({ status: 'logged-out', user: null })
    })
  })

  it('gives the logged-in user', async () => {
    server.use(loggedInAs())
    const { result } = renderUseSession()

    await waitFor(() => {
      expect(result.current).toEqual({ status: 'logged-in', user: testUser })
    })
  })

  it('is an error when the session can’t be loaded', async () => {
    server.use(http.get('/api/session', () => HttpResponse.error()))
    const { result } = renderUseSession()

    await waitFor(() => {
      expect(result.current).toEqual({ status: 'error', user: null })
    })
  })
})

describe('the session gate', () => {
  it('shows a splash until the session loads', async () => {
    const slowly = http.get('/api/session', async () => {
      await delay(50)
      return HttpResponse.json(
        { detail: 'Not logged in', code: 'not_authenticated' },
        { status: 401 },
      )
    })
    renderApp('/login', slowly)

    expect(screen.getByRole('status')).toHaveTextContent('Loading…')
    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('makes writes send the logged-in session’s CSRF token', async () => {
    let sent: string | null = null
    server.use(
      http.post('/api/thing', ({ request }) => {
        sent = request.headers.get('X-CSRF-Token')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderApp('/train', loggedInAs(testUser, 'gate-token'))
    await screen.findByRole('heading', { level: 1, name: 'Train' })

    await apiFetch('/api/thing', { method: 'POST' })

    expect(sent).toBe('gate-token')
  })

  it('offers a retry when the session can’t be loaded', async () => {
    renderApp(
      '/train',
      http.get('/api/session', () => HttpResponse.error(), { once: true }),
      loggedInAs(),
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Couldn’t reach the server')
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Train' })).toBeInTheDocument()
  })
})
