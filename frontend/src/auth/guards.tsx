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
