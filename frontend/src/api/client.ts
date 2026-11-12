// How the app calls the API. Orval's generated hooks send every request through apiFetch
// (see orval.config.ts), so the CSRF header, JSON handling and errors are dealt with here once
import type { ErrorBody } from '@/api/generated/model'

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

let csrfToken: string | null = null

/** Sets the logged-in session's CSRF token (from GET /api/session or logging in), or clears
 * it on logout. Writes send whichever token is current when they're sent */
export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

/** One invalid field from a 422 response */
export interface FieldError {
  /** Where the problem is, as a dotted path without the leading `body`: `name`, `sets.0.reps`
   * (`query.limit` for a query parameter) */
  field: string
  message: string
  /** The kind of problem, e.g. `missing` or `string_too_short` */
  type: string
}

/** The API answered with an error status */
export class ApiError extends Error {
  override readonly name = 'ApiError'
  readonly status: number
  /** Stable and machine-readable, e.g. `not_found` or `duplicate_name` */
  readonly code: string
  /** Human-readable */
  readonly detail: string
  /** Field-level problems, only on 422 responses */
  readonly errors: FieldError[]

  constructor(status: number, body: ErrorBody) {
    super(body.detail)
    this.status = status
    this.code = body.code
    this.detail = body.detail
    this.errors = toFieldErrors(body.errors)
  }
}

/** The request got no response at all: offline, or the connection failed */
export class NetworkError extends Error {
  override readonly name = 'NetworkError'

  constructor(options?: ErrorOptions) {
    super('Couldn’t reach the server', options)
  }
}

/** What a failed request throws. Orval types the hooks' errors with this, passing the error
 * body types, which ApiError already covers */
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- the parameter Orval passes
export type ErrorType<_Body = unknown> = ApiError | NetworkError

/** Whether `error` is an ApiError, optionally with the given code */
export function isApiError(error: unknown, code?: string): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code)
}

/** Calls the API with the session cookie and JSON, adding the CSRF token to writes. Resolves
 * with the parsed body (undefined for 204), or rejects with ApiError or NetworkError. A
 * request cancelled through its signal rejects with the AbortError as usual */
export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (!SAFE_METHODS.has(method) && csrfToken !== null) {
    headers.set('X-CSRF-Token', csrfToken)
  }

  let response: Response
  try {
    response = await fetch(url, { ...init, method, headers, credentials: 'same-origin' })
  } catch (error) {
    if (init.signal?.aborted) throw error
    throw new NetworkError({ cause: error })
  }

  if (!response.ok) throw await toApiError(response)
  const text = await response.text()
  return (text === '' ? undefined : JSON.parse(text)) as T
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = undefined
  }
  if (isErrorBody(body)) return new ApiError(response.status, body)
  // Not from the API itself, e.g. a proxy's 502 page
  return new ApiError(response.status, {
    code: 'http_error',
    detail: response.statusText || `The server answered ${String(response.status)}`,
  })
}

function isErrorBody(body: unknown): body is ErrorBody {
  return (
    typeof body === 'object' &&
    body !== null &&
    'code' in body &&
    typeof body.code === 'string' &&
    'detail' in body &&
    typeof body.detail === 'string'
  )
}

// Validation errors are Pydantic's: {loc: ['body', 'sets', 0, 'reps'], msg, type, ...}
function toFieldErrors(errors: ErrorBody['errors']): FieldError[] {
  return (errors ?? []).flatMap((error) => {
    const { loc, msg, type } = error
    if (!Array.isArray(loc) || typeof msg !== 'string') return []
    const path: unknown[] = loc[0] === 'body' ? loc.slice(1) : loc
    return [
      {
        field: path.map(String).join('.'),
        message: msg,
        type: typeof type === 'string' ? type : 'invalid',
      },
    ]
  })
}
