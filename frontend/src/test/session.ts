// MSW handlers for GET /api/session, which the app loads before showing any page
import { http, HttpResponse } from 'msw'

import type { SessionRead, UserRead } from '@/api/generated/model'

export const testUser: UserRead = {
  id: '6f1c2a4e-5b7d-4c3e-9a8f-1d2e3f4a5b6c',
  username: 'lifter',
  display_name: 'Lifter',
  weight_unit: 'kg',
  is_admin: false,
}

/** An admin, who also sees the Admin tab */
export const adminUser: UserRead = {
  id: '9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d',
  username: 'coach',
  display_name: 'Coach',
  weight_unit: 'kg',
  is_admin: true,
}

export function sessionFor(user: UserRead = testUser, csrfToken = 'csrf-token'): SessionRead {
  return { user, csrf_token: csrfToken }
}

/** Nobody is logged in: the API answers 401 */
export function loggedOut() {
  return http.get('/api/session', () =>
    HttpResponse.json(
      { detail: 'You’re not logged in', code: 'not_authenticated' },
      { status: 401 },
    ),
  )
}

/** `user` is logged in, with `csrfToken` for writes */
export function loggedInAs(user: UserRead = testUser, csrfToken = 'csrf-token') {
  return http.get('/api/session', () => HttpResponse.json(sessionFor(user, csrfToken)))
}
