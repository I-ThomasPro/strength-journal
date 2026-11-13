import { describe, expect, it, vi } from 'vitest'

import { ApiError, NetworkError } from '@/api/client'
import { fieldAria, NETWORK_ERROR_MESSAGE, showRequestError } from '@/lib/forms'

interface Values {
  username: string
  password: string
}

const FIELDS = ['username', 'password'] as const

function errorsShown(error: unknown, codeFields: Record<string, 'username' | 'password'> = {}) {
  const setError = vi.fn()
  showRequestError<Values>(error, setError, FIELDS, codeFields)
  return setError.mock.calls.map(([name, { message }]) => [name, message] as const)
}

describe('showRequestError', () => {
  it('puts a 422’s errors on their fields, and unknown ones at form level', () => {
    const error = new ApiError(422, {
      code: 'invalid',
      detail: 'Request validation failed',
      errors: [
        { loc: ['body', 'username'], msg: 'Too short', type: 'string_too_short' },
        { loc: ['body', 'remember'], msg: 'Not allowed', type: 'extra_forbidden' },
      ],
    })

    expect(errorsShown(error)).toEqual([
      ['username', 'Too short'],
      ['root.serverError', 'Not allowed'],
    ])
  })

  it('puts an error with a mapped code on its field', () => {
    const error = new ApiError(409, {
      code: 'duplicate_username',
      detail: 'That username is taken',
    })

    expect(errorsShown(error, { duplicate_username: 'username' })).toEqual([
      ['username', 'That username is taken'],
    ])
  })

  it.each([
    ['an API error', new ApiError(401, { code: 'invalid_credentials', detail: 'Wrong' }), 'Wrong'],
    ['a network failure', new NetworkError(), NETWORK_ERROR_MESSAGE],
    ['anything else', new TypeError('oops'), 'Something went wrong. Try again.'],
  ])('shows %s at form level', (_, error, message) => {
    expect(errorsShown(error, { duplicate_username: 'username' })).toEqual([
      ['root.serverError', message],
    ])
  })
})

describe('fieldAria', () => {
  it('points at the error, else the hint', () => {
    expect(fieldAria('name', { hint: 'A hint', error: 'Wrong' })).toEqual({
      'aria-invalid': true,
      'aria-describedby': 'name-error',
    })
    expect(fieldAria('name', { hint: 'A hint' })).toEqual({
      'aria-invalid': undefined,
      'aria-describedby': 'name-hint',
    })
    expect(fieldAria('name', {})).toEqual({
      'aria-invalid': undefined,
      'aria-describedby': undefined,
    })
  })
})
