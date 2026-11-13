// A stand-in for GET /api/exercises, for tests of the screens that list exercises
import { http, HttpResponse } from 'msw'

import type { ExerciseRead } from '@/api/generated/model'
import { server } from '@/test/server'

/** One of the user's own exercises, or the library's with `{ library: true }` */
export function exercise(name: string, { library = false } = {}): ExerciseRead {
  return {
    id: `id-${name}`,
    name,
    type: 'strength',
    is_library: library,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-01T10:00:00Z',
  }
}

/** Answers GET /api/exercises like the API does, from `all` (already in name order): by scope,
 * part of the name, and page. It reads `all` on each request, so a test can add to it. Records
 * each request's query */
export function answerExercises(all: ExerciseRead[]) {
  const requests: Record<string, string>[] = []
  server.use(
    http.get('/api/exercises', ({ request }) => {
      const query = new URL(request.url).searchParams
      requests.push(Object.fromEntries(query))
      const scope = query.get('scope') ?? 'all'
      const q = (query.get('q') ?? '').toLowerCase()
      const limit = Number(query.get('limit') ?? 50)
      const offset = Number(query.get('offset') ?? 0)
      const matching = all.filter(
        (item) =>
          (scope === 'all' || item.is_library === (scope === 'library')) &&
          item.name.toLowerCase().includes(q),
      )
      return HttpResponse.json({
        items: matching.slice(offset, offset + limit),
        total: matching.length,
      })
    }),
  )
  return requests
}
