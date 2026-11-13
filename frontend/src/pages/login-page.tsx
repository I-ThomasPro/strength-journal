import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'

import type { SessionRead } from '@/api/generated/model'
import { useSessionCreate } from '@/api/generated/session'
import { sessionQueryKey } from '@/auth/session'
import { FormField, FormMessage } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fieldAria, showRequestError } from '@/lib/forms'

interface LoginValues {
  username: string
  password: string
}

const FIELDS = ['username', 'password'] as const

export function LoginPage() {
  const queryClient = useQueryClient()
  // Try even when the browser says it's offline, so a NetworkError explains it at once rather
  // than the request waiting for the network (TanStack's default)
  const login = useSessionCreate({ mutation: { networkMode: 'always' } })
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ defaultValues: { username: '', password: '' } })

  const onSubmit = handleSubmit(async (values) => {
    let session: SessionRead
    try {
      session = await login.mutateAsync({ data: values })
    } catch (error) {
      showRequestError(error, setError, FIELDS)
      return
    }
    // With the session stored, the session gate sets its CSRF token, and RedirectIfLoggedIn
    // moves on to `?next=` or Train
    queryClient.setQueryData(sessionQueryKey, session)
  })

  return (
    <form noValidate className="space-y-4" onSubmit={(event) => void onSubmit(event)}>
      {errors.root?.serverError && (
        <FormMessage kind="error">{errors.root.serverError.message}</FormMessage>
      )}

      <FormField id="username" label="Username" error={errors.username?.message}>
        <Input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          {...fieldAria('username', { error: errors.username?.message })}
          {...register('username', { required: 'Enter your username' })}
        />
      </FormField>

      <FormField id="password" label="Password" error={errors.password?.message}>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          {...fieldAria('password', { error: errors.password?.message })}
          {...register('password', { required: 'Enter your password' })}
        />
      </FormField>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Logging in…' : 'Log in'}
      </Button>
    </form>
  )
}
