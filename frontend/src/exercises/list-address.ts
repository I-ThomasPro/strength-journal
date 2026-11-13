// How an exercise's page gets back to the Exercises list it was opened from

/** Router state on a link from the list to an exercise: the list's address, with its tab and
 * search */
export interface FromList {
  list: string
}

/** Where an exercise's page links back to: the list as it was (see FromList), or the plain
 * list when the page was opened some other way */
export function listToReturnTo(state: unknown): string {
  if (
    typeof state === 'object' &&
    state !== null &&
    'list' in state &&
    typeof state.list === 'string'
  ) {
    return state.list
  }
  return '/exercises'
}
