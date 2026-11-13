import { ChevronLeft } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'

import { isApiError } from '@/api/client'
import { useExercisesShow } from '@/api/generated/exercises'
import { FormMessage } from '@/components/form-field'
import { OfflineNotice } from '@/components/offline-notice'
import { Button } from '@/components/ui/button'
import { listToReturnTo } from '@/exercises/list-address'
import { requestErrorMessage } from '@/lib/forms'
import { useOnline } from '@/lib/online'

/** The API has no such exercise for this user: 404, or 422 for an id that isn't one */
function isMissing(error: unknown): boolean {
  return isApiError(error) && (error.status === 404 || error.status === 422)
}

/** One exercise: its name, and whether it's the library's or the user's own. Renaming comes
 * with #93, deleting with #87, and its history with #62 */
export function ExercisePage() {
  const { id = '' } = useParams()
  const list = listToReturnTo(useLocation().state)

  return (
    <div className="space-y-4">
      <Link
        to={list}
        className="-ml-1 inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <ChevronLeft aria-hidden="true" className="size-4" />
        Exercises
      </Link>

      <OfflineNotice>You’re offline. Exercises need a connection.</OfflineNotice>
      <ExerciseDetail id={id} />
    </div>
  )
}

function ExerciseDetail({ id }: { id: string }) {
  const online = useOnline()
  const { data: exercise, error, isPending, refetch } = useExercisesShow(id)

  // Offline, the request waits for a connection, and the notice above says why
  if (isPending) {
    return online ? <p className="text-muted-foreground">Loading exercise…</p> : null
  }

  if (exercise === undefined) {
    if (isMissing(error)) {
      return (
        <p className="text-muted-foreground">
          This exercise doesn’t exist. It may have been deleted.
        </p>
      )
    }
    return (
      <div className="space-y-3">
        <FormMessage kind="error">{requestErrorMessage(error)}</FormMessage>
        <Button variant="outline" onClick={() => void refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <h2 className="text-xl font-semibold break-words">{exercise.name}</h2>
      <p className="text-sm text-muted-foreground">
        {exercise.is_library ? 'Library exercise' : 'Your exercise'}
      </p>
    </div>
  )
}
