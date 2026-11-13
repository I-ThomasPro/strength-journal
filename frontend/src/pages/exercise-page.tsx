import { ChevronLeft, Pencil } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'

import { isApiError } from '@/api/client'
import { useExercisesShow } from '@/api/generated/exercises'
import type { ExerciseRead } from '@/api/generated/model'
import { FormMessage } from '@/components/form-field'
import { OfflineNotice } from '@/components/offline-notice'
import { Button } from '@/components/ui/button'
import { listToReturnTo } from '@/exercises/list-address'
import { RenameExerciseForm } from '@/exercises/rename-exercise-form'
import { requestErrorMessage } from '@/lib/forms'
import { useOnline } from '@/lib/online'

/** The API has no such exercise for this user: 404, or 422 for an id that isn't one */
function isMissing(error: unknown): boolean {
  return isApiError(error) && (error.status === 404 || error.status === 422)
}

/** One exercise: its name, and whether it's the library's or the user's own, which can be
 * renamed. Deleting comes with #87, and its history with #62 */
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

  return <ExerciseView exercise={exercise} />
}

function ExerciseView({ exercise }: { exercise: ExerciseRead }) {
  // The form for a new name, and whether it has just saved one
  const [renaming, setRenaming] = useState(false)
  const [renamed, setRenamed] = useState(false)
  const renameButton = useRef<HTMLButtonElement>(null)
  function closeForm() {
    setRenaming(false)
    // Back to where the form was opened from
    renameButton.current?.focus()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h2 className="text-xl font-semibold break-words">{exercise.name}</h2>
          <p className="text-sm text-muted-foreground">
            {exercise.is_library ? 'Library exercise' : 'Your exercise'}
          </p>
        </div>
        {/* The library's exercises are read-only */}
        {!exercise.is_library && (
          <Button
            ref={renameButton}
            variant="outline"
            size="sm"
            aria-expanded={renaming}
            onClick={() => {
              setRenamed(false)
              setRenaming((open) => !open)
            }}
          >
            <Pencil aria-hidden="true" />
            Rename
          </Button>
        )}
      </div>

      {renaming && (
        <RenameExerciseForm
          exercise={exercise}
          onRenamed={() => {
            setRenamed(true)
            closeForm()
          }}
          onCancel={closeForm}
        />
      )}
      {renamed && <FormMessage kind="success">Renamed</FormMessage>}
    </div>
  )
}
