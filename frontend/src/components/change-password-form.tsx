import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { usePasswordUpdate } from '@/api/generated/password'
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT } from '@/auth/password'
import { FormField, FormMessage } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fieldAria, showRequestError } from '@/lib/forms'

interface PasswordValues {
  current_password: string
  new_password: string
  confirm_password: string
}

/** The fields the API gets. The confirmation is only checked here */
const API_FIELDS = ['current_password', 'new_password'] as const

const EMPTY: PasswordValues = { current_password: '', new_password: '', confirm_password: '' }

/** Changes the logged-in user's password (PATCH /api/password). The API logs out their other
 * devices, and this one stays logged in */
export function ChangePasswordForm({ username }: { username: string }) {
  // Try even when the browser says it's offline, so a NetworkError explains it at once
  const updatePassword = usePasswordUpdate({ mutation: { networkMode: 'always' } })
  const [changed, setChanged] = useState(false)
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ defaultValues: EMPTY })

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    try {
      await updatePassword.mutateAsync({ data: { current_password, new_password } })
    } catch (error) {
      // A wrong current password is a 401 `invalid_credentials`, which goes on its field and
      // doesn't end the session (see endSessionIfExpired)
      showRequestError(error, setError, API_FIELDS, { invalid_credentials: 'current_password' })
      return
    }
    reset(EMPTY)
    setChanged(true)
  })

  return (
    <section aria-labelledby="change-password" className="space-y-4">
      <h2 id="change-password" className="text-base font-semibold">
        Change password
      </h2>

      <form
        noValidate
        className="space-y-4"
        onSubmit={(event) => {
          // The confirmation is about the last change, so each new try clears it
          setChanged(false)
          void onSubmit(event)
        }}
      >
        {errors.root?.serverError && (
          <FormMessage kind="error">{errors.root.serverError.message}</FormMessage>
        )}
        {changed && (
          <FormMessage kind="success">
            Password changed. Your other devices were logged out.
          </FormMessage>
        )}

        {/* Not shown: it tells password managers whose password this is, so they update the
            right saved login */}
        <input
          type="text"
          name="username"
          autoComplete="username"
          value={username}
          readOnly
          className="hidden"
        />

        <FormField
          id="current_password"
          label="Current password"
          error={errors.current_password?.message}
        >
          <Input
            id="current_password"
            type="password"
            autoComplete="current-password"
            {...fieldAria('current_password', { error: errors.current_password?.message })}
            {...register('current_password', { required: 'Enter your current password' })}
          />
        </FormField>

        <FormField
          id="new_password"
          label="New password"
          hint={PASSWORD_HINT}
          error={errors.new_password?.message}
        >
          <Input
            id="new_password"
            type="password"
            autoComplete="new-password"
            {...fieldAria('new_password', {
              hint: PASSWORD_HINT,
              error: errors.new_password?.message,
            })}
            {...register('new_password', {
              required: 'Enter a new password',
              minLength: { value: MIN_PASSWORD_LENGTH, message: PASSWORD_HINT },
              // Re-check the confirmation when this changes after a failed try
              deps: ['confirm_password'],
            })}
          />
        </FormField>

        <FormField
          id="confirm_password"
          label="Confirm new password"
          error={errors.confirm_password?.message}
        >
          <Input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            {...fieldAria('confirm_password', { error: errors.confirm_password?.message })}
            {...register('confirm_password', {
              validate: (value, values) =>
                value === values.new_password || 'The passwords don’t match',
            })}
          />
        </FormField>

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Changing…' : 'Change password'}
        </Button>
      </form>
    </section>
  )
}
