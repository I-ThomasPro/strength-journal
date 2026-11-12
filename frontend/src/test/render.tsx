import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'

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
