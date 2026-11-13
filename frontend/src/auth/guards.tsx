import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router'

import { safeNext } from '@/auth/next-path'
import { useSession } from '@/auth/session'

/** Signed-in pages: a logged-out user goes to log in, and comes back here afterwards. It sits
 * under the session gate, so the session has always loaded by now */
export function RequireLogin() {
  const { status } = useSession()
  const { pathname, search, hash } = useLocation()

  if (status === 'logged-out') {
    const next = encodeURIComponent(`${pathname}${search}${hash}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return <Outlet />
}

/** Signed-out pages, such as logging in: a logged-in user goes on to `?next=`, or Train. This
 * is also how the login page moves on once it stores the new session */
export function RedirectIfLoggedIn() {
  const { status } = useSession()
  const [searchParams] = useSearchParams()

  if (status === 'logged-in') {
    return <Navigate to={safeNext(searchParams.get('next')) ?? '/train'} replace />
  }
  return <Outlet />
}

/** Admin-only pages: anyone else gets the not-found page, as if the page didn't exist. It goes
 * to an unknown address rather than showing the not-found page here, so the header's title
 * (from the matched route) says "Page not found" too */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useSession()
  if (!user?.is_admin) return <Navigate to="/not-found" replace />
  return children
}
