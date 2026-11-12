import { describe, expect, it } from 'vitest'

import { ApiError, NetworkError } from '@/api/client'
import { createQueryClient, shouldRetry } from '@/api/query-client'

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
