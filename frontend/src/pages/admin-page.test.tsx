import { onlineManager } from '@tanstack/react-query'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { adminUser, loggedInAs } from '@/test/session'

const PASSWORD = 'a long enough password'

afterEach(() => {
  onlineManager.setOnline(true)
})

/** Answers POST /api/users with `respond`, recording each body sent */
function answerCreates(respond: (body: Record<string, unknown>) => Response | Promise<Response>) {
  const sent: unknown[] = []
  server.use(
    http.post('/api/users', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      sent.push(body)
      return respond(body)
    }),
  )
  return sent
}

function created(body: Record<string, unknown>) {
  return HttpResponse.json(
    { id: 'new-id', weight_unit: 'kg', is_admin: false, ...body, password: undefined },
    { status: 201 },
  )
}

async function openAdmin() {
  const rendered = renderApp('/admin', loggedInAs(adminUser))
  expect(await screen.findByRole('heading', { name: 'New account' })).toBeInTheDocument()
  return rendered
}

async function fillIn({
  username = 'new.lifter',
  displayName = 'New Lifter',
  password = PASSWORD,
}) {
  if (username) await userEvent.type(screen.getByLabelText('Username'), username)
  if (displayName) await userEvent.type(screen.getByLabelText('Display name'), displayName)
  if (password) await userEvent.type(screen.getByLabelText('Password'), password)
}

async function submit() {
  await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
}

describe('the admin section', () => {
  it('is hidden from everyone but admins', async () => {
    const { router } = renderApp('/admin', loggedInAs())

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }),
    ).toBeInTheDocument()
    expect(document.title).toBe('Page not found · Strength Journal')
    expect(router.state.location.pathname).not.toBe('/admin')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
  })

  it('shows admins its tab', async () => {
    await openAdmin()

    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { current: 'page' })).toHaveTextContent('Admin')
    expect(screen.getByRole('heading', { level: 1, name: 'Admin' })).toBeInTheDocument()
  })
})

describe('creating an account', () => {
  it('sends the account, confirms it and clears the form', async () => {
    const sent = answerCreates(created)
    await openAdmin()

    await fillIn({ username: 'New.Lifter' })
    await userEvent.selectOptions(screen.getByLabelText('Weight unit'), 'lb')
    await userEvent.click(screen.getByLabelText('Admin (can create accounts)'))
    await submit()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Created @New.Lifter. They can log in now.',
    )
    expect(sent).toEqual([
      {
        username: 'New.Lifter',
        display_name: 'New Lifter',
        password: PASSWORD,
        weight_unit: 'lb',
        is_admin: true,
      },
    ])
    expect(screen.getByLabelText('Username')).toHaveValue('')
    expect(screen.getByLabelText('Password')).toHaveValue('')
    expect(screen.getByLabelText('Weight unit')).toHaveValue('kg')
    expect(screen.getByLabelText('Admin (can create accounts)')).not.toBeChecked()
  })

  it('defaults to kg and not an admin', async () => {
    const sent = answerCreates(created)
    await openAdmin()

    await fillIn({})
    await submit()

    await screen.findByRole('status')
    expect(sent).toEqual([expect.objectContaining({ weight_unit: 'kg', is_admin: false })])
  })

  it('puts a taken username on its field', async () => {
    answerCreates(() =>
      HttpResponse.json(
        { detail: 'That username is taken', code: 'duplicate_username' },
        { status: 409 },
      ),
    )
    await openAdmin()

    await fillIn({})
    await submit()

    const username = screen.getByLabelText('Username')
    expect(await screen.findByText('That username is taken')).toBeInTheDocument()
    expect(username).toHaveAttribute('aria-invalid', 'true')
    expect(username).toHaveAccessibleDescription('That username is taken')
    expect(username).toHaveValue('new.lifter')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('puts validation errors on their fields', async () => {
    answerCreates(() =>
      HttpResponse.json(
        {
          detail: 'Request validation failed',
          code: 'invalid',
          errors: [
            { type: 'string_pattern_mismatch', loc: ['body', 'username'], msg: 'Bad characters' },
            { type: 'string_too_long', loc: ['body', 'display_name'], msg: 'Too long' },
          ],
        },
        { status: 422 },
      ),
    )
    await openAdmin()

    await fillIn({})
    await submit()

    expect(await screen.findByText('Bad characters')).toBeInTheDocument()
    expect(screen.getByLabelText('Display name')).toHaveAccessibleDescription('Too long')
  })

  it('checks the fields before sending anything', async () => {
    const sent = answerCreates(created)
    await openAdmin()

    await submit()

    expect(await screen.findByText('Enter a username')).toBeInTheDocument()
    expect(screen.getByText('Enter a display name')).toBeInTheDocument()
    expect(screen.getByText('Enter a password')).toBeInTheDocument()

    await fillIn({ password: 'too short' })
    await submit()

    expect(
      await screen.findByText('At least 10 characters', { selector: '.text-destructive' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-invalid', 'true')
    expect(sent).toEqual([])
  })

  it('says so at once when the browser is offline', async () => {
    answerCreates(() => HttpResponse.error())
    await openAdmin()
    onlineManager.setOnline(false)

    await fillIn({})
    await submit()

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
  })

  it('disables the button while creating', async () => {
    answerCreates(async (body) => {
      await delay('infinite')
      return created(body)
    })
    await openAdmin()

    await fillIn({})
    await submit()

    expect(await screen.findByRole('button', { name: 'Creating…' })).toBeDisabled()
  })
})
