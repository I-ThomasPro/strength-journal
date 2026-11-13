import { CircleUser, Dumbbell, History, ListChecks } from 'lucide-react'

/** The tabs in the bottom bar, in order */
export const tabs = [
  { path: '/train', label: 'Train', icon: Dumbbell },
  { path: '/routines', label: 'Routines', icon: ListChecks },
  { path: '/history', label: 'History', icon: History },
  { path: '/profile', label: 'Profile', icon: CircleUser },
] as const
