import { useEffect } from 'react'
import { useMatches } from 'react-router'

export const APP_NAME = 'Strength Journal'

/** What a route can give in its `handle` (see routes.tsx) */
export interface RouteHandle {
  /** Shown in the page's header and in the browser tab */
  title: string
}

function hasTitle(handle: unknown): handle is RouteHandle {
  return (
    typeof handle === 'object' &&
    handle !== null &&
    'title' in handle &&
    typeof handle.title === 'string'
  )
}

/** The title of the deepest matching route that has one. It also goes in the browser tab, as
 * "Train · Strength Journal" */
export function usePageTitle(): string | undefined {
  const title = useMatches()
    .map((match) => match.handle)
    .filter(hasTitle)
    .at(-1)?.title

  useEffect(() => {
    document.title = title === undefined ? APP_NAME : `${title} · ${APP_NAME}`
  }, [title])

  return title
}
