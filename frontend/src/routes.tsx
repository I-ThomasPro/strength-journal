import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '@/components/app-layout'
import { tabs } from '@/navigation'
import { NotFoundPage } from '@/pages/not-found-page'
import { PlaceholderPage } from '@/pages/placeholder-page'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/train" replace /> },
      ...tabs.map((tab) => ({ path: tab.path, element: <PlaceholderPage title={tab.label} /> })),
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
