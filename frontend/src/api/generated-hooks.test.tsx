// The generated hooks working with apiFetch: requests, CSRF and errors, end to end
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, it } from 'vitest'

import { setCsrfToken } from '@/api/client'
import { useHealthShow } from '@/api/generated/health'
import { useProfileUpdate } from '@/api/generated/profile'
import { useSessionCreate } from '@/api/generated/session'
import { renderWithQueryClient } from '@/test/render'
import { server } from '@/test/server'

const user = { id: 'u1', email: 'lifter@example.com', display_name: 'Lifter', weight_unit: 'kg' }

function Health() {
  const { data } = useHealthShow()
  return <p>{data ? `API ${data.status}, database ${data.database}` : 'Checking…'}</p>
}

it('fetches with a generated query hook', async () => {
  server.use(http.get('/api/health', () => HttpResponse.json({ status: 'ok', database: 'ok' })))

  renderWithQueryClient(<Health />)

  expect(await screen.findByText('API ok, database ok')).toBeInTheDocument()
})

function RenameButton() {
  const update = useProfileUpdate()
  return (
    <>
      <button
        type="button"
        onClick={() => {
          update.mutate({ data: { display_name: 'Strong Lifter' } })
        }}
      >
        Rename
      </button>
      {update.data && <p>Renamed to {update.data.display_name}</p>}
    </>
  )
}

it('sends a generated mutation’s body as JSON with the CSRF token', async () => {
  let received: { token: string | null; body: unknown } | undefined
  server.use(
    http.patch('/api/profile', async ({ request }) => {
      const body = (await request.json()) as { display_name: string }
      received = { token: request.headers.get('X-CSRF-Token'), body }
      return HttpResponse.json({ ...user, display_name: body.display_name })
    }),
  )
  setCsrfToken('csrf-token')
  renderWithQueryClient(<RenameButton />)

  await userEvent.click(screen.getByRole('button', { name: 'Rename' }))

  expect(await screen.findByText('Renamed to Strong Lifter')).toBeInTheDocument()
  expect(received).toEqual({ token: 'csrf-token', body: { display_name: 'Strong Lifter' } })
})

function LoginButton() {
  const login = useSessionCreate()
  return (
    <>
      <button
        type="button"
        onClick={() => {
          login.mutate({ data: { email: 'lifter@example.com', password: 'wrong-password' } })
        }}
      >
        Log in
      </button>
      {login.error && (
        <p role="alert">
          {login.error.name === 'ApiError' ? login.error.code : 'offline'}: {login.error.message}
        </p>
      )}
    </>
  )
}

it('gives a generated hook the API’s error', async () => {
  server.use(
    http.post('/api/session', () =>
      HttpResponse.json(
        { detail: 'Wrong email or password', code: 'invalid_credentials' },
        { status: 401 },
      ),
    ),
  )
  renderWithQueryClient(<LoginButton />)

  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'invalid_credentials: Wrong email or password',
  )
})
