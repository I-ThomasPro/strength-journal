import { NavLink, Outlet } from 'react-router'

import { useSession } from '@/auth/session'
import { usePageTitle } from '@/lib/page-title'
import { cn } from '@/lib/utils'
import { tabs } from '@/navigation'

/** Signed-in pages: a header with the page's title, the page in a centered column, and the
 * tab bar fixed along the bottom. Safe-area insets keep both clear of notches and home bars */
export function AppLayout() {
  const title = usePageTitle()
  const { user } = useSession()
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.is_admin === true)

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 border-b bg-background pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-14 w-full max-w-2xl items-center px-4">
          <h1 className="truncate text-lg font-semibold">{title}</h1>
        </div>
      </header>

      {/* Padded by more than the tab bar's height, so the bar never covers the page's end */}
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-[calc(5rem+env(safe-area-inset-bottom))]">
        <Outlet />
      </main>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-10 border-t bg-background pb-[env(safe-area-inset-bottom)]"
      >
        <ul className="mx-auto flex h-16 w-full max-w-2xl">
          {visibleTabs.map(({ path, label, icon: Icon }) => (
            <li key={path} className="flex-1">
              <NavLink
                to={path}
                className={({ isActive }) =>
                  cn(
                    'flex h-full flex-col items-center justify-center gap-1 text-xs font-medium transition-colors',
                    isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon aria-hidden="true" className="size-5" strokeWidth={isActive ? 2.5 : 2} />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
