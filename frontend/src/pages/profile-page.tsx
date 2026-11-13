import { LogOut } from 'lucide-react'

import { logoutErrorMessage, useLogout } from '@/auth/logout'
import { useSession } from '@/auth/session'
import { Button } from '@/components/ui/button'

/** Who's logged in, and logging out. The rest of the profile comes with #56 */
export function ProfilePage() {
  const { user } = useSession()
  const logout = useLogout()

  return (
    <div className="space-y-6">
      {user && (
        <section aria-label="Account" className="space-y-1">
          <p className="text-sm text-muted-foreground">Logged in as</p>
          <p className="font-medium">{user.display_name}</p>
          <p className="text-sm text-muted-foreground">@{user.username}</p>
        </section>
      )}

      {logout.isError && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {logoutErrorMessage(logout.error)}
        </p>
      )}

      <Button
        variant="outline"
        disabled={logout.isPending}
        onClick={() => {
          logout.mutate()
        }}
      >
        <LogOut aria-hidden="true" />
        {logout.isPending ? 'Logging out…' : 'Log out'}
      </Button>
    </div>
  )
}
