import { MutationObserver } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import { ApiError, NetworkError } from '@/api/client'
import { createQueryClient, shouldRetry } from '@/api/query-client'
import { sessionQueryKey } from '@/auth/session'
import { sessionFor } from '@/test/session'

function apiError(status: number) {
  return new ApiError(status, { code: 'any', detail: 'Something went wrong' })
}

describe('shouldRetry', () => {
  it.each([
    ['no response', new NetworkError()],
    ['500', apiError(500)],
    ['503', apiError(503)],
  ])('retries %s up to three times', (_, error) => {
    expect([0, 1, 2, 3].map((failures) => shouldRetry(failures, error))).toEqual([
      true,
      true,
      true,
      false,
    ])
  })

  it.each([400, 401, 403, 404, 409, 422])('never retries a %i', (status) => {
    expect(shouldRetry(0, apiError(status))).toBe(false)
  })

  it('never retries other errors, e.g. a bug in a select function', () => {
    expect(shouldRetry(0, new TypeError('Cannot read properties of undefined'))).toBe(false)
  })
})

it('creates a query client with these defaults', () => {
  const queries = createQueryClient().getDefaultOptions().queries

  expect(queries).toMatchObject({ staleTime: 30_000, retry: shouldRetry })
})

describe('ending an expired session', () => {
  const failures = {
    query: async (queryClient: ReturnType<typeof createQueryClient>, error: Error) => {
      await queryClient
        .query({ queryKey: ['thing'], queryFn: () => Promise.reject(error), retry: false })
        .catch(() => undefined)
    },
    mutation: async (queryClient: ReturnType<typeof createQueryClient>, error: Error) => {
      await new MutationObserver(queryClient, { mutationFn: () => Promise.reject(error) })
        .mutate()
        .catch(() => undefined)
    },
  }

  function loggedInClient() {
    const queryClient = createQueryClient()
    queryClient.setQueryData(sessionQueryKey, sessionFor())
    return queryClient
  }

  it.each(['query', 'mutation'] as const)(
    'forgets the session when a %s gets 401 not_authenticated',
    async (kind) => {
      const queryClient = loggedInClient()

      await failures[kind](
        queryClient,
        new ApiError(401, { code: 'not_authenticated', detail: 'You’re not logged in' }),
      )

      expect(queryClient.getQueryData(sessionQueryKey)).toBeNull()
    },
  )

  it.each([
    ['a wrong password (401 invalid_credentials)', 'invalid_credentials', 401],
    ['403 csrf_failed', 'csrf_failed', 403],
    ['a server error', 'http_error', 500],
  ])('keeps the session after %s', async (_, code, status) => {
    for (const kind of ['query', 'mutation'] as const) {
      const queryClient = loggedInClient()

      await failures[kind](queryClient, new ApiError(status, { code, detail: 'No' }))

      expect(queryClient.getQueryData(sessionQueryKey)).toEqual(sessionFor())
    }
  })

  it('keeps the session when the server can’t be reached', async () => {
    const queryClient = loggedInClient()

    await failures.query(queryClient, new NetworkError())

    expect(queryClient.getQueryData(sessionQueryKey)).toEqual(sessionFor())
  })
})
