// Helpers for react-hook-form forms that send their values to the API
import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { ApiError, NetworkError } from '@/api/client'

export const NETWORK_ERROR_MESSAGE =
  'Couldn’t reach the server. Check your connection and try again.'

/** Shows why a request failed on a form:
 * - a 422's field errors on their fields, when the form has them
 * - an error whose code is in `codeFields` (e.g. `duplicate_username` → `username`) on that field
 * - anything else at form level, as `root.serverError` */
export function showRequestError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
  codeFields: Readonly<Record<string, Path<T>>> = {},
): void {
  if (error instanceof ApiError && error.errors.length > 0) {
    for (const { field, message } of error.errors) {
      setError(fields.find((known) => known === field) ?? 'root.serverError', { message })
    }
    return
  }
  const codeField = error instanceof ApiError ? codeFields[error.code] : undefined
  if (error instanceof ApiError && codeField !== undefined) {
    setError(codeField, { message: error.detail })
    return
  }
  setError('root.serverError', { message: requestErrorMessage(error) })
}

/** A failed request, in words for the user */
export function requestErrorMessage(error: unknown): string {
  if (error instanceof NetworkError) return NETWORK_ERROR_MESSAGE
  if (error instanceof ApiError) return error.detail
  return 'Something went wrong. Try again.'
}

/** Ties an input to its hint or error message (see FormField), for screen readers */
export function fieldAria(id: string, { hint, error }: { hint?: string; error?: string }) {
  return {
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error ? `${id}-error` : hint ? `${id}-hint` : undefined,
  }
}
