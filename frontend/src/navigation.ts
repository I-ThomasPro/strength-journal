import {
  CircleUser,
  Dumbbell,
  History,
  ListChecks,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

export interface Tab {
  path: string
  label: string
  icon: LucideIcon
  /** Shown only to admins */
  adminOnly: boolean
  /** Pages outside `path` that belong to this tab, which stays highlighted on them */
  sections?: readonly string[]
}

/** The tabs in the bottom bar, in order */
export const tabs = [
  { path: '/train', label: 'Train', icon: Dumbbell, adminOnly: false },
  {
    path: '/routines',
    label: 'Routines',
    icon: ListChecks,
    adminOnly: false,
    // The Routines page links to the exercises
    sections: ['/exercises'],
  },
  { path: '/history', label: 'History', icon: History, adminOnly: false },
  { path: '/profile', label: 'Profile', icon: CircleUser, adminOnly: false },
  { path: '/admin', label: 'Admin', icon: ShieldCheck, adminOnly: true },
] as const satisfies readonly Tab[]

/** Whether `pathname` is one of the tab's pages: its own, one under it, or one of its sections */
export function isTabActive(tab: Tab, pathname: string): boolean {
  return [tab.path, ...(tab.sections ?? [])].some(
    (base) => pathname === base || pathname.startsWith(`${base}/`),
  )
}
