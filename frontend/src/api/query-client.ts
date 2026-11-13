import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError, isApiError, NetworkError } from '@/api/client'
import { sessionQueryKey } from '@/auth/session'

/** Retries after the first failure */
const MAX_RETRIES = 3

/** Retry only what might work next time: no response at all, or a server error. A 4xx is the
 * request's own fault, so it fails at once */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_RETRIES) return false
  return error instanceof NetworkError || (error instanceof ApiError && error.status >= 500)
}

/** A request answered 401 `not_authenticated`: the session expired, or was logged out on
 * another device. Forget it, and the route guard sends the user to log in, then back. A 401
 * `invalid_credentials` (a wrong password in a form) never logs anyone out */
export function endSessionIfExpired(queryClient: QueryClient, error: unknown): void {
  if (isApiError(error, 'not_authenticated')) queryClient.setQueryData(sessionQueryKey, null)
}

export function createQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        endSessionIfExpired(queryClient, error)
      },
    }),
    mutationCache: new MutationCache({
      onError: (error) => {
        endSessionIfExpired(queryClient, error)
      },
    }),
    defaultOptions: {
      queries: {
        // Data is fresh for 30 seconds: switching screens doesn't refetch it, but coming
        // back to the app later does
        staleTime: 30_000,
        retry: shouldRetry,
      },
    },
  })
  return queryClient
}
