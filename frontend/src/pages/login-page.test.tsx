import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { apiFetch } from '@/api/client'
import { sessionQueryKey } from '@/auth/session'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { sessionFor, testUser } from '@/test/session'

const PASSWORD = 'a long enough password'

/** Answers POST /api/session with `respond`, recording each body sent */
function answerLogins(respond: () => Response | Promise<Response>) {
  const sent: unknown[] = []
  server.use(
    http.post('/api/session', async ({ request }) => {
      sent.push(await request.json())
      return respond()
    }),
  )
  return sent
}

function loginFails(status: number, body: object) {
  return answerLogins(() => HttpResponse.json(body, { status }))
}

async function logIn(username = 'Lifter', password = PASSWORD) {
  await userEvent.type(await screen.findByLabelText('Username'), username)
  await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('logging in', () => {
  it('stores the session and goes to `next`', async () => {
    const session = sessionFor(testUser, 'new-token')
    const sent = answerLogins(() => HttpResponse.json(session, { status: 201 }))
    const { router, queryClient } = renderApp('/login?next=%2Fhistory%3Fweek%3D2')

    await logIn()

    expect(await screen.findByRole('heading', { level: 1, name: 'History' })).toBeInTheDocument()
    expect(router.state.location).toMatchObject({ pathname: '/history', search: '?week=2' })
    expect(sent).toEqual([{ username: 'Lifter', password: PASSWORD }])
    expect(queryClient.getQueryData(sessionQueryKey)).toEqual(session)

    // Writes now send the new session's CSRF token
    let token: string | null = null
    server.use(
      http.post('/api/thing', ({ request }) => {
        token = request.headers.get('X-CSRF-Token')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await apiFetch('/api/thing', { method: 'POST' })
    expect(token).toBe('new-token')
  })

  it.each([
    ['without a `next`', '/login'],
    ['when `next` points at another site', '/login?next=%2F%2Fevil.example'],
  ])('goes to Train %s', async (_, path) => {
    answerLogins(() => HttpResponse.json(sessionFor(), { status: 201 }))
    const { router } = renderApp(path)

    await logIn()

    expect(await screen.findByRole('heading', { level: 1, name: 'Train' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/train')
  })

  it('says when the username or password is wrong, keeping what was typed', async () => {
    loginFails(401, { detail: 'Wrong username or password', code: 'invalid_credentials' })
    const { router } = renderApp('/login')

    await logIn('Lifter', 'not the password')

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password')
    expect(screen.getByLabelText('Username')).toHaveValue('Lifter')
    expect(router.state.location.pathname).toBe('/login')
  })

  it('puts validation errors on their fields', async () => {
    loginFails(422, {
      detail: 'Request validation failed',
      code: 'invalid',
      errors: [
        { type: 'string_too_long', loc: ['body', 'username'], msg: 'That username is too long' },
        { type: 'extra_forbidden', loc: ['body', 'remember'], msg: 'Something else is wrong' },
      ],
    })
    renderApp('/login')

    await logIn()

    const username = screen.getByLabelText('Username')
    expect(await screen.findByText('That username is too long')).toBeInTheDocument()
    expect(username).toHaveAttribute('aria-invalid', 'true')
    expect(username).toHaveAccessibleDescription('That username is too long')
    expect(screen.getByRole('alert')).toHaveTextContent('Something else is wrong')
  })

  it('says when the server can’t be reached', async () => {
    answerLogins(() => HttpResponse.error())
    renderApp('/login')

    await logIn()

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
  })

  it('asks for both fields before sending anything', async () => {
    const sent = answerLogins(() => HttpResponse.json(sessionFor(), { status: 201 }))
    renderApp('/login')

    await userEvent.click(await screen.findByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Enter your username')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription('Enter your password')
    expect(sent).toEqual([])
  })

  it('disables the button while logging in', async () => {
    answerLogins(async () => {
      await delay('infinite')
      return HttpResponse.json(sessionFor(), { status: 201 })
    })
    renderApp('/login')

    await logIn()

    expect(await screen.findByRole('button', { name: 'Logging in…' })).toBeDisabled()
  })
})
