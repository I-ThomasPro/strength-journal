import { useExercisesIndex } from '@/api/generated/exercises'
import { FormMessage } from '@/components/form-field'
import { OfflineNotice } from '@/components/offline-notice'
import { Button } from '@/components/ui/button'
import { requestErrorMessage } from '@/lib/forms'
import { useOnline } from '@/lib/online'

/** The library's exercises and the user's own, by name. Search, tabs and paging come with #89 */
export function ExercisesPage() {
  return (
    <div className="space-y-4">
      <OfflineNotice>You’re offline. Exercises need a connection.</OfflineNotice>
      <ExerciseList />
    </div>
  )
}

function ExerciseList() {
  const online = useOnline()
  // The first page, which is 50 exercises; "Load more" comes with #89
  const { data, error, isPending, refetch } = useExercisesIndex()

  // Offline, the request waits for a connection, and the notice above says why
  if (isPending) {
    return online ? <p className="text-muted-foreground">Loading exercises…</p> : null
  }

  if (data === undefined) {
    return (
      <div className="space-y-3">
        <FormMessage kind="error">{requestErrorMessage(error)}</FormMessage>
        <Button variant="outline" onClick={() => void refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  if (data.items.length === 0) {
    return <p className="text-muted-foreground">No exercises yet</p>
  }

  return (
    <ul className="divide-y">
      {data.items.map((exercise) => (
        <li key={exercise.id} className="flex items-center justify-between gap-3 py-3">
          <span className="min-w-0 truncate font-medium">{exercise.name}</span>
          <span className="shrink-0 text-xs text-muted-foreground">
            {exercise.is_library ? 'Library' : 'Yours'}
          </span>
        </li>
      ))}
    </ul>
  )
}
