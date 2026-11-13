import { useEffect } from 'react'
import { useForm } from 'react-hook-form'

import { FormField, FormMessage } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fieldAria, showRequestError } from '@/lib/forms'

interface NameValues {
  name: string
}

const FIELDS = ['name'] as const

/** The API's limit for an exercise's name */
const MAX_NAME_LENGTH = 100

/** An exercise's name, with its rules, for the forms that add and rename one. `save` sends the
 * name and rejects as the API client does; a name the user already has (409 `duplicate_name`)
 * goes on the field, and any other failure above it */
export function ExerciseNameForm({
  label,
  defaultName = '',
  submitLabel,
  submittingLabel,
  save,
  onCancel,
}: {
  /** The form's accessible name, e.g. "New exercise" */
  label: string
  defaultName?: string
  submitLabel: string
  submittingLabel: string
  save: (name: string) => Promise<void>
  onCancel: () => void
}) {
  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<NameValues>({ defaultValues: { name: defaultName } })

  // The form has just been opened, so typing can start at once
  useEffect(() => {
    setFocus('name')
  }, [setFocus])

  const onSubmit = handleSubmit(async ({ name }) => {
    try {
      await save(name)
    } catch (error) {
      showRequestError(error, setError, FIELDS, { duplicate_name: 'name' })
    }
  })

  return (
    <form
      noValidate
      aria-label={label}
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
        {/* Nothing to send until the name changes */}
        <Button type="submit" disabled={!isDirty || isSubmitting}>
          {isSubmitting ? submittingLabel : submitLabel}
        </Button>
        <Button type="button" variant="ghost" disabled={isSubmitting} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
