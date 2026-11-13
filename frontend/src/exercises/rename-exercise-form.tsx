import { useQueryClient } from '@tanstack/react-query'

import {
  getExercisesIndexQueryKey,
  getExercisesShowQueryKey,
  useExercisesUpdate,
} from '@/api/generated/exercises'
import type { ExerciseRead } from '@/api/generated/model'
import { ExerciseNameForm } from '@/exercises/exercise-name-form'

/** Renames one of the user's own exercises (PATCH /api/exercises/:id). The exercise's page
 * gets the new name at once, and every list of exercises reloads or starts afresh, before
 * `onRenamed` */
export function RenameExerciseForm({
  exercise,
  onRenamed,
  onCancel,
}: {
  exercise: ExerciseRead
  onRenamed: (exercise: ExerciseRead) => void
  onCancel: () => void
}) {
  const queryClient = useQueryClient()
  // Try even when the browser says it's offline, so a NetworkError explains it at once
  const updateExercise = useExercisesUpdate({ mutation: { networkMode: 'always' } })

  return (
    <ExerciseNameForm
      label="Rename exercise"
      defaultName={exercise.name}
      submitLabel="Save"
      submittingLabel="Saving…"
      save={async (name) => {
        const renamed = await updateExercise.mutateAsync({ id: exercise.id, data: { name } })
        queryClient.setQueryData(getExercisesShowQueryKey(exercise.id), renamed)
        // A list that isn't on screen would show the old name when it's next opened, until it
        // reloaded. Forgetting it makes it load afresh instead
        const lists = { queryKey: getExercisesIndexQueryKey() }
        queryClient.removeQueries({ ...lists, type: 'inactive' })
        await queryClient.invalidateQueries(lists)
        onRenamed(renamed)
      }}
      onCancel={onCancel}
    />
  )
}
