import { CircleUser, Dumbbell, History, ListChecks, ShieldCheck } from 'lucide-react'

/** The tabs in the bottom bar, in order. `adminOnly` tabs show only to admins */
export const tabs = [
  { path: '/train', label: 'Train', icon: Dumbbell, adminOnly: false },
  { path: '/routines', label: 'Routines', icon: ListChecks, adminOnly: false },
  { path: '/history', label: 'History', icon: History, adminOnly: false },
  { path: '/profile', label: 'Profile', icon: CircleUser, adminOnly: false },
  { path: '/admin', label: 'Admin', icon: ShieldCheck, adminOnly: true },
] as const
