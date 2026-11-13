import { Dumbbell } from 'lucide-react'
import { useEffect } from 'react'
import { Outlet } from 'react-router'

import { setCsrfToken } from '@/api/client'
import { useSessionQuery } from '@/auth/session'
import { Button } from '@/components/ui/button'

/** The root route: loads who's logged in before showing any page, and keeps the CSRF token
 * that writes send in step with the session */
export function SessionGate() {
  const { data: session, status, isFetching, refetch } = useSessionQuery()

  useEffect(() => {
    setCsrfToken(session?.csrf_token ?? null)
  }, [session])

  if (session !== undefined) return <Outlet />
  if (status === 'pending') return <Splash />
  return (
    <main className="flex min-h-dvh items-center justify-center px-4">
      <div role="alert" className="max-w-sm space-y-4 text-center">
        <h1 className="text-lg font-semibold">Couldn’t reach the server</h1>
        <p className="text-muted-foreground">Check your connection, then try again.</p>
        <Button disabled={isFetching} onClick={() => void refetch()}>
          {isFetching ? 'Retrying…' : 'Retry'}
        </Button>
      </div>
    </main>
  )
}

function Splash() {
  return (
    <div
      role="status"
      className="flex min-h-dvh flex-col items-center justify-center gap-3 text-muted-foreground"
    >
      <Dumbbell aria-hidden="true" className="size-10 animate-pulse text-foreground" />
      <p>Loading…</p>
    </div>
  )
}
