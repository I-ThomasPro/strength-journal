import type { ReactNode } from 'react'

import { Label } from '@/components/ui/label'

/** A labelled input with an optional hint, replaced by its error message when it has one.
 * Give the input `id` and `{...fieldAria(id, {hint, error})}` so the messages are announced */
export function FormField({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  hint?: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-sm text-muted-foreground">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

/** A form-level message: an error (`role="alert"`) or a confirmation (`role="status"`) */
export function FormMessage({
  kind,
  children,
}: {
  kind: 'error' | 'success'
  children: ReactNode
}) {
  return kind === 'error' ? (
    <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {children}
    </p>
  ) : (
    <p role="status" className="rounded-md bg-muted px-3 py-2 text-sm">
      {children}
    </p>
  )
}
