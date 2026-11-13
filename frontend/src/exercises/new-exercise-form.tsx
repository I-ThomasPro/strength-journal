import { useQueryClient } from '@tanstack/react-query'

import { getExercisesIndexQueryKey, useExercisesCreate } from '@/api/generated/exercises'
import type { ExerciseRead } from '@/api/generated/model'
import { ExerciseNameForm } from '@/exercises/exercise-name-form'

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

  return (
    <ExerciseNameForm
      label="New exercise"
      submitLabel="Add exercise"
      submittingLabel="Adding…"
      save={async (name) => {
        const exercise = await createExercise.mutateAsync({ data: { name } })
        // Every search and page of the list starts with this key
        await queryClient.invalidateQueries({ queryKey: getExercisesIndexQueryKey() })
        onCreated(exercise)
      }}
      onCancel={onCancel}
    />
  )
}
