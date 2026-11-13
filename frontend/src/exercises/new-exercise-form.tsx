import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'

import { getExercisesIndexQueryKey, useExercisesCreate } from '@/api/generated/exercises'
import type { ExerciseRead } from '@/api/generated/model'
import { FormField, FormMessage } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fieldAria, showRequestError } from '@/lib/forms'

interface NewExerciseValues {
  name: string
}

const FIELDS = ['name'] as const

/** The API's limit for an exercise's name */
const MAX_NAME_LENGTH = 100

/** Adds one of the user's own exercises (POST /api/exercises): a name, and always a strength
 * exercise for now. Every list of exercises reloads before `onCreated` gets the new one */
export function NewExerciseForm({
  onCreated,
  onCancel,
}: {
  onCreated: (exercise: ExerciseRead) => void
  onCancel: () => void
}) {
  const queryClient = useQueryClient()
  // Try even when the browser says it's offline, so a NetworkError explains it at once
  const createExercise = useExercisesCreate({ mutation: { networkMode: 'always' } })
  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<NewExerciseValues>({ defaultValues: { name: '' } })

  // The form has just been opened, so typing can start at once
  useEffect(() => {
    setFocus('name')
  }, [setFocus])

  const onSubmit = handleSubmit(async (values) => {
    let exercise: ExerciseRead
    try {
      exercise = await createExercise.mutateAsync({ data: values })
    } catch (error) {
      showRequestError(error, setError, FIELDS, { duplicate_name: 'name' })
      return
    }
    // Every search and page of the list starts with this key
    await queryClient.invalidateQueries({ queryKey: getExercisesIndexQueryKey() })
    onCreated(exercise)
  })

  return (
    <form
      noValidate
      aria-label="New exercise"
      className="space-y-4 rounded-md border p-4"
      onSubmit={(event) => void onSubmit(event)}
    >
      {errors.root?.serverError && (
        <FormMessage kind="error">{errors.root.serverError.message}</FormMessage>
      )}

      <FormField id="exercise-name" label="Name" error={errors.name?.message}>
        <Input
          id="exercise-name"
          autoComplete="off"
          enterKeyHint="done"
          {...fieldAria('exercise-name', { error: errors.name?.message })}
          {...register('name', {
            validate: (value) => value.trim() !== '' || 'Enter a name',
            maxLength: {
              value: MAX_NAME_LENGTH,
              message: `At most ${String(MAX_NAME_LENGTH)} characters`,
            },
          })}
        />
      </FormField>

      <div className="flex gap-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Adding…' : 'Add exercise'}
        </Button>
        <Button type="button" variant="ghost" disabled={isSubmitting} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
