import { QueryClient } from '@tanstack/react-query'

import { ApiError, NetworkError } from '@/api/client'

/** Retries after the first failure */
const MAX_RETRIES = 3

/** Retry only what might work next time: no response at all, or a server error. A 4xx is the
 * request's own fault, so it fails at once */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_RETRIES) return false
  return error instanceof NetworkError || (error instanceof ApiError && error.status >= 500)
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Data is fresh for 30 seconds: switching screens doesn't refetch it, but coming
        // back to the app later does
        staleTime: 30_000,
        retry: shouldRetry,
      },
    },
  })
}
