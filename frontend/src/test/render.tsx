import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { RequestHandler } from 'msw'
import type { ReactElement } from 'react'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { routes } from '@/routes'
import { server } from '@/test/server'
import { loggedOut } from '@/test/session'

/** Renders `ui` with its own query client, which doesn't retry, so failures show at once */
export function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    queryClient,
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
  }
}

/** Renders the app's routes at `path` in a memory router, with its own query client. The API
 * answers with `handlers` first, then as if nobody is logged in */
export function renderApp(path: string, ...handlers: RequestHandler[]) {
  server.use(...handlers, loggedOut())
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return { router, ...renderWithQueryClient(<RouterProvider router={router} />) }
}
