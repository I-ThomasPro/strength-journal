import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { WeightUnit, type UserRead } from '@/api/generated/model'
import { useUsersCreate } from '@/api/generated/users'
import { FormField, FormMessage } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WeightUnitSelect } from '@/components/weight-unit-select'
import { fieldAria, showRequestError } from '@/lib/forms'

interface NewAccountValues {
  username: string
  display_name: string
  password: string
  weight_unit: WeightUnit
  is_admin: boolean
}

const FIELDS = ['username', 'display_name', 'password', 'weight_unit', 'is_admin'] as const

const EMPTY: NewAccountValues = {
  username: '',
  display_name: '',
  password: '',
  weight_unit: WeightUnit.kg,
  is_admin: false,
}

/** The API's minimum (MIN_PASSWORD_LENGTH in backend/app/auth/security.py) */
const MIN_PASSWORD_LENGTH = 10

const USERNAME_HINT = '3 to 32 letters, digits, dots, underscores or hyphens'
const PASSWORD_HINT = `At least ${String(MIN_PASSWORD_LENGTH)} characters`

/** Admins create accounts here (POST /api/users); RequireAdmin keeps everyone else out */
export function AdminPage() {
  // Try even when the browser says it's offline, so a NetworkError explains it at once
  const createUser = useUsersCreate({ mutation: { networkMode: 'always' } })
  const [created, setCreated] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<NewAccountValues>({ defaultValues: EMPTY })

  const onSubmit = handleSubmit(async (values) => {
    setCreated(null)
    let user: UserRead
    try {
      user = await createUser.mutateAsync({ data: values })
    } catch (error) {
      showRequestError(error, setError, FIELDS, { duplicate_username: 'username' })
      return
    }
    reset(EMPTY)
    setCreated(user.username)
  })

  return (
    <section aria-labelledby="new-account" className="space-y-4">
      <h2 id="new-account" className="text-base font-semibold">
        New account
      </h2>

      {created && (
        <FormMessage kind="success">Created @{created}. They can log in now.</FormMessage>
      )}

      <form noValidate className="space-y-4" onSubmit={(event) => void onSubmit(event)}>
        {errors.root?.serverError && (
          <FormMessage kind="error">{errors.root.serverError.message}</FormMessage>
        )}

        <FormField
          id="username"
          label="Username"
          hint={USERNAME_HINT}
          error={errors.username?.message}
        >
          <Input
            id="username"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            {...fieldAria('username', { hint: USERNAME_HINT, error: errors.username?.message })}
            {...register('username', { required: 'Enter a username' })}
          />
        </FormField>

        <FormField id="display_name" label="Display name" error={errors.display_name?.message}>
          <Input
            id="display_name"
            autoComplete="off"
            {...fieldAria('display_name', { error: errors.display_name?.message })}
            {...register('display_name', { required: 'Enter a display name' })}
          />
        </FormField>

        <FormField
          id="password"
          label="Password"
          hint={PASSWORD_HINT}
          error={errors.password?.message}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...fieldAria('password', { hint: PASSWORD_HINT, error: errors.password?.message })}
            {...register('password', {
              required: 'Enter a password',
              minLength: { value: MIN_PASSWORD_LENGTH, message: PASSWORD_HINT },
            })}
          />
        </FormField>

        <FormField id="weight_unit" label="Weight unit" error={errors.weight_unit?.message}>
          <WeightUnitSelect
            id="weight_unit"
            {...fieldAria('weight_unit', { error: errors.weight_unit?.message })}
            {...register('weight_unit')}
          />
        </FormField>

        <div className="flex items-center gap-2">
          <input
            id="is_admin"
            type="checkbox"
            className="size-4 accent-primary"
            {...register('is_admin')}
          />
          <Label htmlFor="is_admin">Admin (can create accounts)</Label>
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Creating…' : 'Create account'}
        </Button>
      </form>
    </section>
  )
}
