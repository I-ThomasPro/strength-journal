import { MutationObserver } from '@tanstack/react-query'
import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { apiFetch } from '@/api/client'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs, sessionFor } from '@/test/session'

async function logIn() {
  server.use(http.post('/api/session', () => HttpResponse.json(sessionFor(), { status: 201 })))
  await userEvent.type(await screen.findByLabelText('Username'), 'lifter')
  await userEvent.type(screen.getByLabelText('Password'), 'a long enough password')
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

/** /api/thing answers every request with a 401 carrying `code` */
function thingAnswers401(code: string) {
  server.use(
    http.all('/api/thing', () =>
      HttpResponse.json({ detail: 'Not allowed', code }, { status: 401 }),
    ),
  )
}

describe('signed-in pages', () => {
  it('send a logged-out user to log in, and back afterwards', async () => {
    const { router } = renderApp('/history?week=2')

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location).toMatchObject({
      pathname: '/login',
      search: `?next=${encodeURIComponent('/history?week=2')}`,
    })
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()

    await logIn()

    expect(await screen.findByRole('heading', { level: 1, name: 'History' })).toBeInTheDocument()
    expect(router.state.location).toMatchObject({ pathname: '/history', search: '?week=2' })
  })

  it('show to a logged-in user', async () => {
    const { router } = renderApp('/routines', loggedInAs())

    expect(await screen.findByRole('heading', { level: 1, name: 'Routines' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/routines')
  })
})

describe('the login page, for a logged-in user', () => {
  it.each([
    ['Train', '/login', '/train'],
    ['`next`', '/login?next=%2Froutines', '/routines'],
    ['Train when `next` points at another site', '/login?next=%2F%2Fevil.example', '/train'],
  ])('moves on to %s', async (_, path, expected) => {
    const { router } = renderApp(path, loggedInAs())

    await screen.findByRole('navigation', { name: 'Main' })
    expect(router.state.location.pathname).toBe(expected)
  })
})

describe('an expired session', () => {
  it('sends the user to log in when a query gets 401 not_authenticated', async () => {
    const { router, queryClient } = renderApp('/routines?tab=mine', loggedInAs())
    await screen.findByRole('heading', { level: 1, name: 'Routines' })
    thingAnswers401('not_authenticated')

    await act(async () => {
      await queryClient
        .query({ queryKey: ['thing'], queryFn: () => apiFetch('/api/thing') })
        .catch(() => undefined)
    })

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.search).toBe(`?next=${encodeURIComponent('/routines?tab=mine')}`)
  })

  it('sends the user to log in when a write gets 401 not_authenticated', async () => {
    const { router, queryClient } = renderApp('/profile', loggedInAs())
    await screen.findByRole('heading', { level: 1, name: 'Profile' })
    thingAnswers401('not_authenticated')

    await act(async () => {
      await new MutationObserver(queryClient, {
        mutationFn: () => apiFetch('/api/thing', { method: 'POST' }),
      })
        .mutate()
        .catch(() => undefined)
    })

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.search).toBe(`?next=${encodeURIComponent('/profile')}`)
  })

  it('isn’t a wrong password: 401 invalid_credentials keeps the user logged in', async () => {
    const { router, queryClient } = renderApp('/profile', loggedInAs())
    await screen.findByRole('heading', { level: 1, name: 'Profile' })
    thingAnswers401('invalid_credentials')

    await act(async () => {
      await new MutationObserver(queryClient, {
        mutationFn: () => apiFetch('/api/thing', { method: 'PATCH' }),
      })
        .mutate()
        .catch(() => undefined)
    })

    expect(screen.getByRole('heading', { level: 1, name: 'Profile' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/profile')
  })
})
