import { useEffect, useState } from 'react'

/** `value`, once it has stopped changing for `delayMs`: e.g. a search box's text, so a request
 * goes out when the typing pauses, not on every key */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(value)
    }, delayMs)
    return () => {
      clearTimeout(timer)
    }
  }, [value, delayMs])

  return debounced
}
