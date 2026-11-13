// Who's logged in. The session lives in the TanStack Query cache under the generated key for
// GET /api/session, so logging in and out update it with setQueryData(sessionQueryKey, …)
import { useQuery } from '@tanstack/react-query'

import { isApiError } from '@/api/client'
import type { SessionRead, UserRead } from '@/api/generated/model'
import { getSessionShowQueryKey, sessionShow } from '@/api/generated/session'

export const sessionQueryKey = getSessionShowQueryKey()

/** The session, or null when nobody is logged in: GET /api/session answers 401 then, which is
 * an expected answer here, not a failure. Network and server errors still fail (and retry) */
async function loadSession(signal: AbortSignal): Promise<SessionRead | null> {
  try {
    return await sessionShow({ signal })
  } catch (error) {
    if (isApiError(error, 'not_authenticated')) return null
    throw error
  }
}

export function useSessionQuery() {
  return useQuery({ queryKey: sessionQueryKey, queryFn: ({ signal }) => loadSession(signal) })
}

export type SessionStatus = 'loading' | 'logged-in' | 'logged-out' | 'error'

/** Who's logged in. `error` means the session couldn't be loaded at all (e.g. offline) */
export function useSession(): { status: SessionStatus; user: UserRead | null } {
  const { data, status } = useSessionQuery()
  if (data === null) return { status: 'logged-out', user: null }
  if (data !== undefined) return { status: 'logged-in', user: data.user }
  return { status: status === 'pending' ? 'loading' : 'error', user: null }
}
