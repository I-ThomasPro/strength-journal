import { useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import type { SessionRead, UserRead, WeightUnit } from '@/api/generated/model'
import { useProfileUpdate } from '@/api/generated/profile'
import { logoutErrorMessage, useLogout } from '@/auth/logout'
import { sessionQueryKey, useSession } from '@/auth/session'
import { FormField, FormMessage } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { WeightUnitSelect } from '@/components/weight-unit-select'
import { fieldAria, showRequestError } from '@/lib/forms'

/** Who's logged in, their settings, and logging out. Changing the password comes with #82 */
export function ProfilePage() {
  const { user } = useSession()
  const logout = useLogout()

  return (
    <div className="space-y-8">
      {user && (
        <>
          <section aria-label="Account" className="space-y-1">
            <p className="text-sm text-muted-foreground">Logged in as</p>
            <p className="font-medium">{user.display_name}</p>
            <p className="text-sm text-muted-foreground">@{user.username}</p>
          </section>
          {/* A new form for each user, so it starts from their settings */}
          <ProfileForm key={user.id} user={user} />
        </>
      )}

      <section aria-label="Log out" className="space-y-4">
        {logout.isError && (
          <FormMessage kind="error">{logoutErrorMessage(logout.error)}</FormMessage>
        )}
        <Button
          variant="outline"
          disabled={logout.isPending}
          onClick={() => {
            logout.mutate()
          }}
        >
          <LogOut aria-hidden="true" />
          {logout.isPending ? 'Logging out…' : 'Log out'}
        </Button>
      </section>
    </div>
  )
}

interface ProfileValues {
  display_name: string
  weight_unit: WeightUnit
}

const FIELDS = ['display_name', 'weight_unit'] as const

/** The API's limit for a display name */
const MAX_DISPLAY_NAME_LENGTH = 100

function ProfileForm({ user }: { user: UserRead }) {
  const queryClient = useQueryClient()
  // Try even when the browser says it's offline, so a NetworkError explains it at once
  const updateProfile = useProfileUpdate({ mutation: { networkMode: 'always' } })
  const [saved, setSaved] = useState(false)
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<ProfileValues>({
    defaultValues: { display_name: user.display_name, weight_unit: user.weight_unit },
  })

  const onSubmit = handleSubmit(async (values) => {
    setSaved(false)
    let updated: UserRead
    try {
      updated = await updateProfile.mutateAsync({ data: values })
    } catch (error) {
      showRequestError(error, setError, FIELDS)
      return
    }
    // The session holds the user everywhere else in the app, e.g. "Logged in as" above
    queryClient.setQueryData<SessionRead | null>(sessionQueryKey, (session) =>
      session ? { ...session, user: updated } : session,
    )
    reset({ display_name: updated.display_name, weight_unit: updated.weight_unit })
    setSaved(true)
  })

  return (
    <section aria-labelledby="settings" className="space-y-4">
      <h2 id="settings" className="text-base font-semibold">
        Settings
      </h2>

      <form noValidate className="space-y-4" onSubmit={(event) => void onSubmit(event)}>
        {errors.root?.serverError && (
          <FormMessage kind="error">{errors.root.serverError.message}</FormMessage>
        )}
        {saved && !isDirty && <FormMessage kind="success">Saved</FormMessage>}

        <FormField id="display_name" label="Display name" error={errors.display_name?.message}>
          <Input
            id="display_name"
            autoComplete="name"
            {...fieldAria('display_name', { error: errors.display_name?.message })}
            {...register('display_name', {
              validate: (value) => value.trim() !== '' || 'Enter a display name',
              maxLength: {
                value: MAX_DISPLAY_NAME_LENGTH,
                message: `At most ${String(MAX_DISPLAY_NAME_LENGTH)} characters`,
              },
            })}
          />
        </FormField>

        <FormField
          id="weight_unit"
          label="Weight unit"
          hint="For new sets and records"
          error={errors.weight_unit?.message}
        >
          <WeightUnitSelect
            id="weight_unit"
            {...fieldAria('weight_unit', {
              hint: 'For new sets and records',
              error: errors.weight_unit?.message,
            })}
            {...register('weight_unit')}
          />
        </FormField>

        <Button type="submit" disabled={!isDirty || isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Save'}
        </Button>
      </form>
    </section>
  )
}
