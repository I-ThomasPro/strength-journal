import { onlineManager } from '@tanstack/react-query'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { sessionQueryKey } from '@/auth/session'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs, sessionFor, testUser } from '@/test/session'

const OLD_PASSWORD = 'the old long password'
const NEW_PASSWORD = 'a brand new password'

afterEach(() => {
  onlineManager.setOnline(true)
})

/** Answers PATCH /api/password with `respond` (204 unless given), recording each body and
 * CSRF header */
function answerPasswordChanges(
  respond: () => Response = () => new HttpResponse(null, { status: 204 }),
) {
  const sent: { token: string | null; body: unknown }[] = []
  server.use(
    http.patch('/api/password', async ({ request }) => {
      sent.push({ token: request.headers.get('X-CSRF-Token'), body: await request.json() })
      return respond()
    }),
  )
  return sent
}

/** The form is on the Profile tab */
async function openProfile() {
  const rendered = renderApp('/profile', loggedInAs(testUser, 'the-token'))
  expect(await screen.findByRole('heading', { name: 'Change password' })).toBeInTheDocument()
  return rendered
}

async function fillIn({
  current = OLD_PASSWORD,
  next = NEW_PASSWORD,
  confirm = next,
}: { current?: string; next?: string; confirm?: string } = {}) {
  await userEvent.type(screen.getByLabelText('Current password'), current)
  await userEvent.type(screen.getByLabelText('New password'), next)
  await userEvent.type(screen.getByLabelText('Confirm new password'), confirm)
}

async function submit() {
  await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
}

describe('changing the password', () => {
  it('sends the current and new passwords, then clears the form', async () => {
    const sent = answerPasswordChanges()
    await openProfile()

    await fillIn()
    await submit()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Password changed. Your other devices were logged out.',
    )
    expect(sent).toEqual([
      {
        token: 'the-token',
        body: { current_password: OLD_PASSWORD, new_password: NEW_PASSWORD },
      },
    ])
    expect(screen.getByLabelText('Current password')).toHaveValue('')
    expect(screen.getByLabelText('New password')).toHaveValue('')
    expect(screen.getByLabelText('Confirm new password')).toHaveValue('')

    // The next try clears the confirmation
    await submit()
    expect(await screen.findByText('Enter your current password')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(sent).toHaveLength(1)
  })

  it('puts a wrong current password on its field, and keeps the user logged in', async () => {
    answerPasswordChanges(() =>
      HttpResponse.json(
        { detail: 'Your current password is wrong', code: 'invalid_credentials' },
        { status: 401 },
      ),
    )
    const { router, queryClient } = await openProfile()

    await fillIn()
    await submit()

    expect(await screen.findByText('Your current password is wrong')).toBeInTheDocument()
    const current = screen.getByLabelText('Current password')
    expect(current).toHaveAttribute('aria-invalid', 'true')
    expect(current).toHaveAccessibleDescription('Your current password is wrong')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    expect(router.state.location.pathname).toBe('/profile')
    expect(screen.getByText('@lifter')).toBeInTheDocument()
    expect(queryClient.getQueryData(sessionQueryKey)).toEqual(sessionFor(testUser, 'the-token'))
  })

  it.each([
    [
      'don’t match',
      { confirm: 'a different password' },
      'Confirm new password',
      'The passwords don’t match',
    ],
    ['is too short', { next: 'too short' }, 'New password', 'At least 10 characters'],
  ])('flags new passwords that %s, without sending them', async (_, values, label, message) => {
    const sent = answerPasswordChanges()
    await openProfile()

    await fillIn(values)
    await submit()

    const field = screen.getByLabelText(label)
    await waitFor(() => {
      expect(field).toHaveAttribute('aria-invalid', 'true')
    })
    expect(field).toHaveAccessibleDescription(message)
    expect(sent).toEqual([])
  })

  it('says so at once when the browser is offline', async () => {
    answerPasswordChanges(() => HttpResponse.error())
    await openProfile()
    onlineManager.setOnline(false)

    await fillIn()
    await submit()

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
