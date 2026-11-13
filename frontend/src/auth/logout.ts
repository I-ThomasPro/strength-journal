import { hashKey, useQueryClient } from '@tanstack/react-query'

import { isApiError, NetworkError } from '@/api/client'
import { useSessionDestroy } from '@/api/generated/session'
import { sessionQueryKey } from '@/auth/session'

/** Logs out (DELETE /api/session), then forgets everything cached for this user, so none of it
 * shows after the next login, and sets the session to null: the session gate clears the CSRF
 * token, and the route guard goes to /login. A session that had already expired (401) is
 * forgotten all the same; any other failure, such as being offline, leaves the user logged in */
export function useLogout() {
  const queryClient = useQueryClient()

  function forgetSession() {
    // Update the session query the gate and guards watch, rather than removing it: a removed
    // query's watchers would never see the new one
    queryClient.setQueryData(sessionQueryKey, null)
    const sessionHash = hashKey(sessionQueryKey)
    queryClient.removeQueries({ predicate: (query) => query.queryHash !== sessionHash })
  }

  return useSessionDestroy({
    mutation: {
      // Try even when the browser says it's offline, rather than waiting for the network
      // (TanStack's default): the user should hear now that they're still logged in
      networkMode: 'always',
      onSuccess: forgetSession,
      onError: (error) => {
        if (isApiError(error, 'not_authenticated')) forgetSession()
      },
    },
  })
}

/** Why logging out failed, for the user. The user is still logged in */
export function logoutErrorMessage(error: unknown): string {
  if (error instanceof NetworkError) {
    return 'Couldn’t reach the server, so you’re still logged in. Try again when you’re back online.'
  }
  return 'Couldn’t log out. Try again.'
}
