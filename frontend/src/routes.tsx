import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/components/app-layout'
import { PublicLayout } from '@/components/public-layout'
import type { RouteHandle } from '@/lib/page-title'
import { tabs } from '@/navigation'
import { NotFoundPage } from '@/pages/not-found-page'
import { PlaceholderPage } from '@/pages/placeholder-page'
import { RootErrorPage, RouteErrorPage } from '@/pages/route-error-page'

/** A route's title, for its layout's header and the browser tab (see usePageTitle) */
function titled(title: string): RouteHandle {
  return { title }
}

export const routes: RouteObject[] = [
  {
    // If a layout itself fails
    errorElement: <RootErrorPage />,
    children: [
      {
        element: <PublicLayout />,
        // A placeholder until logging in is built (#67)
        children: [{ path: '/login', element: <PlaceholderPage />, handle: titled('Log in') }],
      },
      {
        path: '/',
        element: <AppLayout />,
        children: [
          {
            // A page that fails shows the error inside the layout, so the tab bar still works
            errorElement: <RouteErrorPage />,
            children: [
              { index: true, element: <Navigate to="/train" replace /> },
              ...tabs.map((tab) => ({
                path: tab.path,
                element: <PlaceholderPage />,
                handle: titled(tab.label),
              })),
              { path: '*', element: <NotFoundPage />, handle: titled('Page not found') },
            ],
          },
        ],
      },
    ],
  },
]
