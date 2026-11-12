import { NavLink, Outlet } from 'react-router'

import { cn } from '@/lib/utils'
import { tabs } from '@/navigation'

/** The current page, with the tab bar fixed along the bottom */
export function AppLayout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <main className="flex-1 px-4 pt-6 pb-24">
        <Outlet />
      </main>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 border-t bg-background pb-[env(safe-area-inset-bottom)]"
      >
        <ul className="mx-auto grid max-w-md grid-cols-4">
          {tabs.map((tab) => (
            <li key={tab.path}>
              <NavLink
                to={tab.path}
                className={({ isActive }) =>
                  cn(
                    'flex h-14 items-center justify-center text-sm',
                    isActive ? 'font-semibold text-foreground' : 'text-muted-foreground',
                  )
                }
              >
                {tab.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
