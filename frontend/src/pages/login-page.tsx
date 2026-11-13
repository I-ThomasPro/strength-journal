import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router'

import { ApiError, NetworkError } from '@/api/client'
import type { SessionRead } from '@/api/generated/model'
import { useSessionCreate } from '@/api/generated/session'
import { safeNext } from '@/auth/next-path'
import { sessionQueryKey } from '@/auth/session'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface LoginValues {
  username: string
  password: string
}

const FIELDS = ['username', 'password'] as const

export function LoginPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const login = useSessionCreate()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ defaultValues: { username: '', password: '' } })

  function showError(error: unknown) {
    if (error instanceof ApiError && error.errors.length > 0) {
      for (const { field, message } of error.errors) {
        const name = FIELDS.find((known) => known === field)
        setError(name ?? 'root.serverError', { message })
      }
    } else if (error instanceof NetworkError) {
      setError('root.serverError', {
        message: 'Couldn’t reach the server. Check your connection and try again.',
      })
    } else {
      setError('root.serverError', {
        message: error instanceof ApiError ? error.detail : 'Something went wrong. Try again.',
      })
    }
  }

  const onSubmit = handleSubmit(async (values) => {
    let session: SessionRead
    try {
      session = await login.mutateAsync({ data: values })
    } catch (error) {
      showError(error)
      return
    }
    // The session gate sees the new session in the cache and sets its CSRF token
    queryClient.setQueryData(sessionQueryKey, session)
    await navigate(safeNext(searchParams.get('next')) ?? '/train', { replace: true })
  })

  return (
    <form noValidate className="space-y-4" onSubmit={(event) => void onSubmit(event)}>
      {errors.root?.serverError && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errors.root.serverError.message}
        </p>
      )}

      <div className="space-y-2">
        <Label htmlFor="username">Username</Label>
        <Input
          id="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          aria-invalid={errors.username ? true : undefined}
          aria-describedby={errors.username ? 'username-error' : undefined}
          {...register('username', { required: 'Enter your username' })}
        />
        {errors.username && (
          <p id="username-error" className="text-sm text-destructive">
            {errors.username.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? 'password-error' : undefined}
          {...register('password', { required: 'Enter your password' })}
        />
        {errors.password && (
          <p id="password-error" className="text-sm text-destructive">
            {errors.password.message}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Logging in…' : 'Log in'}
      </Button>
    </form>
  )
}
