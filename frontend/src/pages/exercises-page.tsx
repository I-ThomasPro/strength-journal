import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import { Scope } from '@/api/generated/model'
import { FormMessage } from '@/components/form-field'
import { OfflineNotice } from '@/components/offline-notice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useExercisePages } from '@/exercises/exercise-pages'
import { useDebouncedValue } from '@/lib/debounce'
import { requestErrorMessage } from '@/lib/forms'
import { useOnline } from '@/lib/online'
import { cn } from '@/lib/utils'

const SCOPE_TABS = [
  { scope: Scope.all, label: 'All' },
  { scope: Scope.library, label: 'Library' },
  { scope: Scope.mine, label: 'Mine' },
] as const

/** How long the typing pauses before a search goes out */
const SEARCH_DELAY_MS = 300

/** The API's limit for `q` */
const MAX_SEARCH_LENGTH = 100

function toScope(value: string | null): Scope {
  return SCOPE_TABS.find((tab) => tab.scope === value)?.scope ?? Scope.all
}

/** `params` with `name` set to `value`, or without it when that's the default */
function withParam(
  params: URLSearchParams,
  name: string,
  value: string,
  defaultValue = '',
): URLSearchParams {
  const next = new URLSearchParams(params)
  if (value === defaultValue) next.delete(name)
  else next.set(name, value)
  return next
}

/** The library's exercises and the user's own, by tab and search. Both are kept in the address
 * (`?scope=mine&q=squat`), so a reload or coming back shows the same list */
export function ExercisesPage() {
  const [params, setParams] = useSearchParams()
  const scope = toScope(params.get('scope'))
  const q = params.get('q') ?? ''

  // The box shows each key at once; the address, and so the request, follows when typing pauses
  const [text, setText] = useState(q)
  const search = useDebouncedValue(text, SEARCH_DELAY_MS).trim()
  useEffect(() => {
    if (search === q) return
    setParams((current) => withParam(current, 'q', search), { replace: true })
  }, [search, q, setParams])

  return (
    <div className="space-y-4">
      <OfflineNotice>You’re offline. Exercises need a connection.</OfflineNotice>

      <div>
        <Label htmlFor="exercise-search" className="sr-only">
          Search exercises
        </Label>
        <Input
          id="exercise-search"
          type="search"
          placeholder="Search exercises"
          autoComplete="off"
          enterKeyHint="search"
          maxLength={MAX_SEARCH_LENGTH}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
          }}
        />
      </div>

      <Tabs
        value={scope}
        onValueChange={(value) => {
          setParams((current) => withParam(current, 'scope', toScope(value), Scope.all), {
            replace: true,
          })
        }}
      >
        <TabsList aria-label="Which exercises" className="w-full">
          {SCOPE_TABS.map((tab) => (
            <TabsTrigger key={tab.scope} value={tab.scope}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {/* One panel, which belongs to whichever tab is selected */}
        <TabsContent value={scope}>
          <ExerciseList scope={scope} q={q} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function emptyMessage(scope: Scope, q: string): string {
  if (q !== '') return `No exercises match “${q}”`
  if (scope === Scope.library) return 'The library has no exercises yet'
  if (scope === Scope.mine) return 'You haven’t added any exercises yet'
  return 'No exercises yet'
}

function ExerciseList({ scope, q }: { scope: Scope; q: string }) {
  const online = useOnline()
  const {
    data,
    error,
    isPending,
    isPlaceholderData,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
    refetch,
  } = useExercisePages(scope, q)

  const loading = <p className="text-muted-foreground">Loading exercises…</p>

  // Offline, the request waits for a connection, and the notice above says why. The last
  // results would stand in until then, under a tab or search they don't belong to
  if (!online && (isPending || isPlaceholderData)) return null
  if (isPending) return loading

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

  const exercises = data.pages.flatMap((page) => page.items)
  if (exercises.length === 0) {
    // While the last results are standing in, they say nothing about this search
    return isPlaceholderData ? (
      loading
    ) : (
      <p className="text-muted-foreground">{emptyMessage(scope, q)}</p>
    )
  }

  return (
    <div className="space-y-4">
      <ul className={cn('divide-y', isPlaceholderData && 'opacity-60')}>
        {exercises.map((exercise) => (
          <li key={exercise.id} className="flex items-center justify-between gap-3 py-3">
            <span className="min-w-0 truncate font-medium">{exercise.name}</span>
            {/* The other tabs hold one kind only */}
            {scope === Scope.all && (
              <span className="shrink-0 text-xs text-muted-foreground">
                {exercise.is_library ? 'Library' : 'Yours'}
              </span>
            )}
          </li>
        ))}
      </ul>

      {isFetchNextPageError && <FormMessage kind="error">{requestErrorMessage(error)}</FormMessage>}
      {hasNextPage && !isPlaceholderData && (
        <Button
          variant="outline"
          className="w-full"
          disabled={isFetchingNextPage || !online}
          onClick={() => void fetchNextPage()}
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </Button>
      )}
    </div>
  )
}
