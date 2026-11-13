import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query'

import { exercisesIndex, getExercisesIndexQueryKey } from '@/api/generated/exercises'
import type { Scope } from '@/api/generated/model'

/** How many exercises each request asks for (the API's default) */
export const EXERCISE_PAGE_SIZE = 50

/** Exercises in `scope` whose name contains `q`, ordered by name and loaded a page at a time:
 * `fetchNextPage()` loads the next one while `hasNextPage`. A new scope or search keeps showing
 * the last results (`isPlaceholderData`) until its own arrive */
export function useExercisePages(scope: Scope, q: string) {
  const params = { scope, ...(q === '' ? {} : { q }), limit: EXERCISE_PAGE_SIZE }

  return useInfiniteQuery({
    // Starts like the generated hook's key, so invalidating `/api/exercises` covers these too
    queryKey: [...getExercisesIndexQueryKey(params), 'pages'],
    queryFn: ({ pageParam, signal }) =>
      exercisesIndex({ ...params, offset: pageParam }, { signal }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((count, page) => count + page.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
    placeholderData: keepPreviousData,
  })
}
