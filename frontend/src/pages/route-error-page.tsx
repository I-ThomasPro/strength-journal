import { RotateCw } from 'lucide-react'
import { isRouteErrorResponse, useRouteError } from 'react-router'

import { Button } from '@/components/ui/button'
import { reloadPage } from '@/lib/reload'

/** Shown in place of a page that failed to render, inside the layout */
export function RouteErrorPage() {
  const error = useRouteError()

  return (
    <div role="alert" className="space-y-4">
      <h2 className="text-lg font-semibold">Something went wrong</h2>
      <p className="text-muted-foreground">
        This page couldn’t be shown. Reloading usually fixes it.
      </p>
      {import.meta.env.DEV && (
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{describe(error)}</pre>
      )}
      <Button onClick={reloadPage}>
        <RotateCw aria-hidden="true" />
        Reload
      </Button>
    </div>
  )
}

/** Shown on its own when a layout itself fails */
export function RootErrorPage() {
  return (
    <main className="mx-auto max-w-md px-4 py-[max(2rem,env(safe-area-inset-top))]">
      <RouteErrorPage />
    </main>
  )
}

function describe(error: unknown): string {
  if (isRouteErrorResponse(error)) return `${String(error.status)} ${error.statusText}`
  if (error instanceof Error) return error.stack ?? error.message
  return String(error)
}
