import { Dumbbell } from 'lucide-react'
import { Outlet } from 'react-router'

import { APP_NAME, usePageTitle } from '@/lib/page-title'

/** Signed-out pages, such as logging in: a centered card under the app's name, with no tab bar */
export function PublicLayout() {
  const title = usePageTitle()

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted px-4 py-[max(2rem,env(safe-area-inset-top))]">
      <main className="w-full max-w-sm space-y-6">
        <p className="flex items-center justify-center gap-2 text-2xl font-semibold tracking-tight">
          <Dumbbell aria-hidden="true" className="size-7" />
          {APP_NAME}
        </p>
        <section className="space-y-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm">
          <h1 className="text-lg font-semibold">{title}</h1>
          <Outlet />
        </section>
      </main>
    </div>
  )
}
