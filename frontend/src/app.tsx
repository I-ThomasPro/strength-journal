import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import { createQueryClient } from '@/api/query-client'
import { routes } from '@/routes'

const queryClient = createQueryClient()
const router = createBrowserRouter(routes)

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      {/* Only in development; production builds leave it out */}
      <ReactQueryDevtools buttonPosition="top-right" />
    </QueryClientProvider>
  )
}
