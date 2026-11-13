import { onlineManager } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'

/** Whether the browser is online, as TanStack Query sees it: its queries wait while it isn't */
export function useOnline(): boolean {
  return useSyncExternalStore(
    (onChange) => onlineManager.subscribe(onChange),
    () => onlineManager.isOnline(),
  )
}
