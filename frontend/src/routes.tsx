import type { ReactElement } from 'react'
import { Navigate, type RouteObject } from 'react-router'

import { RedirectIfLoggedIn, RequireAdmin, RequireLogin } from '@/auth/guards'
import { SessionGate } from '@/auth/session-gate'
import { AppLayout } from '@/components/app-layout'
import { PublicLayout } from '@/components/public-layout'
import type { RouteHandle } from '@/lib/page-title'
import { tabs } from '@/navigation'
import { AdminPage } from '@/pages/admin-page'
import { ExercisesPage } from '@/pages/exercises-page'
import { LoginPage } from '@/pages/login-page'
import { NotFoundPage } from '@/pages/not-found-page'
import { PlaceholderPage } from '@/pages/placeholder-page'
import { ProfilePage } from '@/pages/profile-page'
import { RoutinesPage } from '@/pages/routines-page'
import { RootErrorPage, RouteErrorPage } from '@/pages/route-error-page'

/** Each tab's page; placeholders until their screens are built */
const tabPages: Record<(typeof tabs)[number]['path'], ReactElement> = {
  '/train': <PlaceholderPage />,
  '/routines': <RoutinesPage />,
  '/history': <PlaceholderPage />,
  '/profile': <ProfilePage />,
  '/admin': (
    <RequireAdmin>
      <AdminPage />
    </RequireAdmin>
  ),
}

/** A route's title, for its layout's header and the browser tab (see usePageTitle) */
function titled(title: string): RouteHandle {
  return { title }
}

export const routes: RouteObject[] = [
  {
    // Loads who's logged in before any page shows
    element: <SessionGate />,
    // If the gate or a layout fails
    errorElement: <RootErrorPage />,
    children: [
      {
        // Signed-out pages: a logged-in user moves on to `?next=` or Train
        element: <RedirectIfLoggedIn />,
        children: [
          {
            element: <PublicLayout />,
            children: [{ path: '/login', element: <LoginPage />, handle: titled('Log in') }],
          },
        ],
      },
      {
        // Signed-in pages: a logged-out user goes to log in first
        element: <RequireLogin />,
        children: [
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
                    element: tabPages[tab.path],
                    handle: titled(tab.label),
                  })),
                  // Opened from the Routines tab, which stays highlighted (see navigation.ts)
                  { path: '/exercises', element: <ExercisesPage />, handle: titled('Exercises') },
                  { path: '*', element: <NotFoundPage />, handle: titled('Page not found') },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
]
