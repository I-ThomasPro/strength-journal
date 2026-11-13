import { WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'

import { useOnline } from '@/lib/online'

/** For screens that need a connection: shows its message while the browser is offline, and
 * nothing otherwise */
export function OfflineNotice({ children }: { children: ReactNode }) {
  const online = useOnline()
  if (online) return null

  return (
    <p role="status" className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm">
      <WifiOff aria-hidden="true" className="size-4 shrink-0" />
      {children}
    </p>
  )
}
