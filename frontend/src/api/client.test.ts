import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ApiError, apiFetch, isApiError, NetworkError, setCsrfToken } from '@/api/client'
import { server } from '@/test/server'

/** Answers every request to /api/thing with 204, recording its method and CSRF header */
function recordCsrfHeaders() {
  const seen: [string, string | null][] = []
  server.use(
    http.all('/api/thing', ({ request }) => {
      seen.push([request.method, request.headers.get('X-CSRF-Token')])
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return seen
}

async function failure(request: Promise<unknown>): Promise<unknown> {
  return request.then(
    () => {
      throw new Error('The request should have failed')
    },
    (error: unknown) => error,
  )
}

describe('apiFetch', () => {
  it('asks for JSON and returns the parsed body', async () => {
    let accept: string | null = null
    server.use(
      http.get('/api/thing', ({ request }) => {
        accept = request.headers.get('Accept')
        return HttpResponse.json({ name: 'Squat' })
      }),
    )

    await expect(apiFetch('/api/thing')).resolves.toEqual({ name: 'Squat' })
    expect(accept).toBe('application/json')
  })

  it('sends a JSON body as JSON', async () => {
    let received: { type: string | null; body: unknown } | undefined
    server.use(
      http.post('/api/thing', async ({ request }) => {
        received = { type: request.headers.get('Content-Type'), body: await request.json() }
        return HttpResponse.json({ id: 1 }, { status: 201 })
      }),
    )

    await apiFetch('/api/thing', { method: 'POST', body: JSON.stringify({ name: 'Squat' }) })

    expect(received).toEqual({ type: 'application/json', body: { name: 'Squat' } })
  })

  it('sends the CSRF token on writes, never on reads', async () => {
    const seen = recordCsrfHeaders()
    setCsrfToken('token-1')

    for (const method of ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']) {
      await apiFetch('/api/thing', { method })
    }

    expect(seen).toEqual([
      ['GET', null],
      ['POST', 'token-1'],
      ['PUT', 'token-1'],
      ['PATCH', 'token-1'],
      ['DELETE', 'token-1'],
    ])
  })

  it('sends the token that’s current when the request goes out', async () => {
    const seen = recordCsrfHeaders()

    await apiFetch('/api/thing', { method: 'POST' })
    setCsrfToken('after-login')
    await apiFetch('/api/thing', { method: 'POST' })
    setCsrfToken(null)
    await apiFetch('/api/thing', { method: 'POST' })

    expect(seen.map(([, token]) => token)).toEqual([null, 'after-login', null])
  })

  it('returns undefined for 204 No Content', async () => {
    recordCsrfHeaders()

    await expect(apiFetch('/api/thing', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('turns an error body into an ApiError with its field errors', async () => {
    server.use(
      http.post('/api/thing', () =>
        HttpResponse.json(
          {
            detail: 'Request validation failed',
            code: 'invalid',
            errors: [
              { type: 'missing', loc: ['body', 'name'], msg: 'Field required' },
              { type: 'greater_than', loc: ['body', 'sets', 0, 'reps'], msg: 'Too few' },
              { type: 'int_parsing', loc: ['query', 'limit'], msg: 'Not a number' },
              { unexpected: 'shape' },
            ],
          },
          { status: 422 },
        ),
      ),
    )

    const error = await failure(apiFetch('/api/thing', { method: 'POST', body: '{}' }))

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      name: 'ApiError',
      status: 422,
      code: 'invalid',
      detail: 'Request validation failed',
      message: 'Request validation failed',
      errors: [
        { field: 'name', message: 'Field required', type: 'missing' },
        { field: 'sets.0.reps', message: 'Too few', type: 'greater_than' },
        { field: 'query.limit', message: 'Not a number', type: 'int_parsing' },
      ],
    })
    expect(isApiError(error, 'invalid')).toBe(true)
    expect(isApiError(error, 'not_found')).toBe(false)
  })

  it('gives an error without field errors an empty list', async () => {
    server.use(
      http.post('/api/thing', () =>
        HttpResponse.json(
          { detail: 'You already have an exercise with that name', code: 'duplicate_name' },
          { status: 409 },
        ),
      ),
    )

    const error = await failure(apiFetch('/api/thing', { method: 'POST' }))

    expect(error).toMatchObject({ status: 409, code: 'duplicate_name', errors: [] })
  })

  it('turns a response that isn’t from the API into an http_error', async () => {
    server.use(
      http.get(
        '/api/thing',
        () =>
          new HttpResponse('<h1>Bad Gateway</h1>', {
            status: 502,
            statusText: 'Bad Gateway',
            headers: { 'Content-Type': 'text/html' },
          }),
      ),
    )

    const error = await failure(apiFetch('/api/thing'))

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 502, code: 'http_error', detail: 'Bad Gateway' })
  })

  it('throws a NetworkError when no response arrives', async () => {
    server.use(http.get('/api/thing', () => HttpResponse.error()))

    const error = await failure(apiFetch('/api/thing'))

    expect(error).toBeInstanceOf(NetworkError)
    expect((error as NetworkError).cause).toBeInstanceOf(TypeError)
    expect(isApiError(error)).toBe(false)
  })

  it('lets a cancelled request reject with its AbortError', async () => {
    server.use(
      http.get('/api/thing', async () => {
        await delay('infinite')
        return HttpResponse.json({})
      }),
    )
    const controller = new AbortController()

    const request = failure(apiFetch('/api/thing', { signal: controller.signal }))
    controller.abort()

    expect(await request).toMatchObject({ name: 'AbortError' })
  })
})
