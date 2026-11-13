import { onlineManager } from '@tanstack/react-query'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import type { ExerciseRead } from '@/api/generated/model'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs } from '@/test/session'

afterEach(() => {
  onlineManager.setOnline(true)
})

function exercise(name: string, { library = false } = {}): ExerciseRead {
  return {
    id: `id-${name}`,
    name,
    type: 'strength',
    is_library: library,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-01T10:00:00Z',
  }
}

const EXERCISES = [
  exercise('Back Squat', { library: true }),
  exercise('Bench Press', { library: true }),
  exercise('Front Squat', { library: true }),
  exercise('Zercher Squat'),
  exercise('Zottman Curl'),
]

/** Answers GET /api/exercises like the API does, from `all` (already in name order): by scope,
 * part of the name, and page. Records each request's query */
function answerExercises(all: ExerciseRead[] = EXERCISES) {
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

function openExercises(path = '/exercises') {
  return renderApp(path, loggedInAs())
}

/** The selected tab's panel, which holds the list */
const panel = () => within(screen.getByRole('tabpanel'))

/** Waits for the list to show exactly these rows, each as its text */
async function expectRows(expected: string[]) {
  await waitFor(() => {
    expect(
      panel()
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual(expected)
  })
}

/** Waits for the list to show this many rows */
async function expectRowCount(count: number) {
  await waitFor(() => {
    expect(panel().getAllByRole('listitem')).toHaveLength(count)
  })
}

const searchBox = () => screen.getByRole('searchbox', { name: 'Search exercises' })

describe('the exercises list', () => {
  it('shows the library’s exercises and the user’s own, by name', async () => {
    const requests = answerExercises()
    openExercises()

    await expectRows([
      'Back SquatLibrary',
      'Bench PressLibrary',
      'Front SquatLibrary',
      'Zercher SquatYours',
      'Zottman CurlYours',
    ])
    expect(screen.getByRole('heading', { level: 1, name: 'Exercises' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
    expect(requests).toEqual([{ scope: 'all', limit: '50', offset: '0' }])
  })

  it('opens from the Routines tab, which stays current', async () => {
    answerExercises()
    const { router } = renderApp('/routines', loggedInAs())

    await userEvent.click(await screen.findByRole('link', { name: 'Exercises' }))

    await expectRowCount(EXERCISES.length)
    expect(router.state.location.pathname).toBe('/exercises')
    expect(document.title).toBe('Exercises · Strength Journal')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { current: 'page' })).toHaveTextContent('Routines')
  })

  it('switches between all, the library and the user’s own, kept in the address', async () => {
    answerExercises()
    const { router } = openExercises()
    await expectRowCount(EXERCISES.length)

    await userEvent.click(screen.getByRole('tab', { name: 'Mine' }))
    await expectRows(['Zercher Squat', 'Zottman Curl'])
    expect(screen.getByRole('tab', { name: 'Mine' })).toHaveAttribute('aria-selected', 'true')
    expect(router.state.location.search).toBe('?scope=mine')

    await userEvent.click(screen.getByRole('tab', { name: 'Library' }))
    await expectRows(['Back Squat', 'Bench Press', 'Front Squat'])
    expect(router.state.location.search).toBe('?scope=library')

    await userEvent.click(screen.getByRole('tab', { name: 'All' }))
    await expectRowCount(EXERCISES.length)
    expect(router.state.location.search).toBe('')
  })

  it('searches by name once the typing pauses, kept in the address', async () => {
    const requests = answerExercises()
    const { router } = openExercises()
    await expectRowCount(EXERCISES.length)

    await userEvent.type(searchBox(), 'squat')
    await expectRows(['Back SquatLibrary', 'Front SquatLibrary', 'Zercher SquatYours'])
    expect(router.state.location.search).toBe('?q=squat')
    // One search for the word, not one for each letter
    expect(requests.map((request) => request.q)).toEqual([undefined, 'squat'])

    await userEvent.clear(searchBox())
    await expectRowCount(EXERCISES.length)
    expect(router.state.location.search).toBe('')
  })

  it('starts from the tab and search in the address', async () => {
    const requests = answerExercises()
    openExercises('/exercises?scope=mine&q=curl')

    await expectRows(['Zottman Curl'])
    expect(searchBox()).toHaveValue('curl')
    expect(screen.getByRole('tab', { name: 'Mine' })).toHaveAttribute('aria-selected', 'true')
    expect(requests).toEqual([{ scope: 'mine', q: 'curl', limit: '50', offset: '0' }])
  })

  it('loads more, a page at a time', async () => {
    const many = Array.from({ length: 60 }, (_, index) =>
      exercise(`Exercise ${String(index + 1).padStart(2, '0')}`),
    )
    const requests = answerExercises(many)
    openExercises()

    await expectRowCount(50)

    await userEvent.click(screen.getByRole('button', { name: 'Load more' }))
    await expectRowCount(60)
    expect(panel().getAllByRole('listitem').at(-1)).toHaveTextContent('Exercise 60')
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
    expect(requests.map((request) => request.offset)).toEqual(['0', '50'])
  })

  it.each([
    ['/exercises', 'No exercises yet'],
    ['/exercises?scope=library', 'The library has no exercises yet'],
    ['/exercises?scope=mine', 'You haven’t added any exercises yet'],
    ['/exercises?q=deadlift', 'No exercises match “deadlift”'],
  ])('says when %s has nothing to show', async (path, message) => {
    answerExercises([])
    openExercises(path)

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(panel().queryByRole('list')).not.toBeInTheDocument()
  })

  it('says when the list didn’t load, and tries again', async () => {
    server.use(
      http.get('/api/exercises', () =>
        HttpResponse.json({ detail: 'Something broke', code: 'http_error' }, { status: 500 }),
      ),
    )
    openExercises()

    expect(await screen.findByRole('alert')).toHaveTextContent('Something broke')

    answerExercises()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await expectRowCount(EXERCISES.length)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('says it needs a connection while offline, then loads', async () => {
    const requests = answerExercises()
    // The app is already open when the connection drops
    renderApp('/routines', loggedInAs())
    const link = await screen.findByRole('link', { name: 'Exercises' })
    onlineManager.setOnline(false)
    await userEvent.click(link)

    expect(await screen.findByRole('status')).toHaveTextContent(
      'You’re offline. Exercises need a connection.',
    )
    expect(screen.queryByText('Loading exercises…')).not.toBeInTheDocument()
    expect(requests).toEqual([])

    act(() => {
      onlineManager.setOnline(true)
    })

    await expectRowCount(EXERCISES.length)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('doesn’t leave another tab’s exercises standing in while offline', async () => {
    answerExercises()
    openExercises()
    await expectRowCount(EXERCISES.length)

    act(() => {
      onlineManager.setOnline(false)
    })
    await userEvent.click(screen.getByRole('tab', { name: 'Mine' }))

    expect(await screen.findByRole('status')).toHaveTextContent('You’re offline')
    expect(panel().queryByRole('list')).not.toBeInTheDocument()

    act(() => {
      onlineManager.setOnline(true)
    })
    await expectRows(['Zercher Squat', 'Zottman Curl'])
  })
})
