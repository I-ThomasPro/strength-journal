import { onlineManager } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { apiFetch } from '@/api/client'
import { sessionQueryKey } from '@/auth/session'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs, sessionFor, testUser } from '@/test/session'

/** Answers DELETE /api/session with `respond`, recording the CSRF header of each request */
function answerLogouts(respond: () => Response | Promise<Response>) {
  const tokens: (string | null)[] = []
  server.use(
    http.delete('/api/session', ({ request }) => {
      tokens.push(request.headers.get('X-CSRF-Token'))
      return respond()
    }),
  )
  return tokens
}

/** The CSRF header a write sends now */
async function csrfHeaderSent(): Promise<string | null> {
  let token: string | null = null
  server.use(
    http.post('/api/thing', ({ request }) => {
      token = request.headers.get('X-CSRF-Token')
      return new HttpResponse(null, { status: 204 })
    }),
  )
  await apiFetch('/api/thing', { method: 'POST' })
  return token
}

afterEach(() => {
  onlineManager.setOnline(true)
})

async function openProfile() {
  const rendered = renderApp('/profile', loggedInAs(testUser, 'old-token'))
  expect(await screen.findByText('@lifter')).toBeInTheDocument()
  return rendered
}

describe('logging out', () => {
  it('forgets the session, its CSRF token and everything cached, before the next login', async () => {
    const tokens = answerLogouts(() => new HttpResponse(null, { status: 204 }))
    const { router, queryClient } = await openProfile()
    expect(screen.getByText('Lifter')).toBeInTheDocument()
    // Something this user loaded earlier
    queryClient.setQueryData(['/api/exercises'], { items: [{ name: 'Lifter’s squat' }], total: 1 })

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(tokens).toEqual(['old-token'])
    expect(queryClient.getQueryData(sessionQueryKey)).toBeNull()
    expect(queryClient.getQueryData(['/api/exercises'])).toBeUndefined()
    expect(await csrfHeaderSent()).toBeNull()

    // The next person to log in sees only their own account
    const coach = { ...testUser, id: 'a-different-id', username: 'coach', display_name: 'Coach' }
    server.use(
      http.post('/api/session', () =>
        HttpResponse.json(sessionFor(coach, 'new-token'), { status: 201 }),
      ),
    )
    await userEvent.type(screen.getByLabelText('Username'), 'coach')
    await userEvent.type(screen.getByLabelText('Password'), 'a long enough password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('@coach')).toBeInTheDocument()
    expect(screen.queryByText('@lifter')).not.toBeInTheDocument()
    expect(queryClient.getQueryData(['/api/exercises'])).toBeUndefined()
    expect(await csrfHeaderSent()).toBe('new-token')
  })

  it('logs out locally when the session had already expired', async () => {
    answerLogouts(() =>
      HttpResponse.json(
        { detail: 'You’re not logged in', code: 'not_authenticated' },
        { status: 401 },
      ),
    )
    const { router, queryClient } = await openProfile()

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(queryClient.getQueryData(sessionQueryKey)).toBeNull()
  })

  it.each([
    [
      'the server can’t be reached',
      () => HttpResponse.error(),
      'Couldn’t reach the server, so you’re still logged in',
    ],
    [
      'the server fails',
      () => HttpResponse.json({ detail: 'Something broke', code: 'http_error' }, { status: 500 }),
      'Couldn’t log out. Try again.',
    ],
  ])('keeps the user logged in, and says why, when %s', async (_, respond, message) => {
    answerLogouts(respond)
    const { router, queryClient } = await openProfile()

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByText('@lifter')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/profile')
    expect(queryClient.getQueryData(sessionQueryKey)).toEqual(sessionFor(testUser, 'old-token'))
    expect(await csrfHeaderSent()).toBe('old-token')
  })

  it('says so at once when the browser is offline, rather than waiting', async () => {
    answerLogouts(() => HttpResponse.error())
    await openProfile()
    onlineManager.setOnline(false)

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
    expect(screen.getByText('@lifter')).toBeInTheDocument()
  })

  it('disables the button while logging out', async () => {
    answerLogouts(async () => {
      await delay('infinite')
      return new HttpResponse(null, { status: 204 })
    })
    await openProfile()

    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('button', { name: 'Logging out…' })).toBeDisabled()
  })
})

/** Answers PATCH /api/profile like the API, recording each body and CSRF header */
function answerProfileUpdates(respond?: () => Response | Promise<Response>) {
  const sent: { token: string | null; body: unknown }[] = []
  server.use(
    http.patch('/api/profile', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      sent.push({ token: request.headers.get('X-CSRF-Token'), body })
      return respond ? respond() : HttpResponse.json({ ...testUser, ...body })
    }),
  )
  return sent
}

describe('profile settings', () => {
  it('start from the user’s own, with Save off until something changes', async () => {
    await openProfile()

    expect(screen.getByLabelText('Display name')).toHaveValue('Lifter')
    expect(screen.getByLabelText('Weight unit')).toHaveValue('kg')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('save, and show the new name everywhere', async () => {
    const sent = answerProfileUpdates()
    const { queryClient } = await openProfile()

    await userEvent.clear(screen.getByLabelText('Display name'))
    await userEvent.type(screen.getByLabelText('Display name'), 'Strong Lifter')
    await userEvent.selectOptions(screen.getByLabelText('Weight unit'), 'lb')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved')
    expect(sent).toEqual([
      { token: 'old-token', body: { display_name: 'Strong Lifter', weight_unit: 'lb' } },
    ])
    expect(screen.getByRole('region', { name: 'Account' })).toHaveTextContent('Strong Lifter')
    expect(queryClient.getQueryData(sessionQueryKey)).toMatchObject({
      user: { display_name: 'Strong Lifter', weight_unit: 'lb' },
    })
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()

    // Editing again hides "Saved"
    await userEvent.type(screen.getByLabelText('Display name'), '!')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('need a display name, checked before sending', async () => {
    const sent = answerProfileUpdates()
    await openProfile()

    await userEvent.clear(screen.getByLabelText('Display name'))
    await userEvent.type(screen.getByLabelText('Display name'), '   ')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Enter a display name')).toBeInTheDocument()
    expect(screen.getByLabelText('Display name')).toHaveAttribute('aria-invalid', 'true')
    expect(sent).toEqual([])
  })

  it('show validation errors on their fields', async () => {
    answerProfileUpdates(() =>
      HttpResponse.json(
        {
          detail: 'Request validation failed',
          code: 'invalid',
          errors: [{ type: 'string_too_long', loc: ['body', 'display_name'], msg: 'Too long' }],
        },
        { status: 422 },
      ),
    )
    await openProfile()

    await userEvent.type(screen.getByLabelText('Display name'), ' the Strong')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Too long')).toBeInTheDocument()
    expect(screen.getByLabelText('Display name')).toHaveAccessibleDescription('Too long')
  })

  it('say so at once when the browser is offline', async () => {
    answerProfileUpdates(() => HttpResponse.error())
    await openProfile()
    onlineManager.setOnline(false)

    await userEvent.selectOptions(screen.getByLabelText('Weight unit'), 'lb')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
    expect(screen.getByRole('region', { name: 'Account' })).toHaveTextContent('Lifter')
  })
})
