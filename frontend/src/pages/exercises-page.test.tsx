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
  exercise('Zercher Squat'),
]

/** Answers GET /api/exercises with `items`, recording each request's query string */
function answerExercises(items: ExerciseRead[] = EXERCISES) {
  const requests: string[] = []
  server.use(
    http.get('/api/exercises', ({ request }) => {
      requests.push(new URL(request.url).search)
      return HttpResponse.json({ items, total: items.length })
    }),
  )
  return requests
}

/** Waits for the list to show exactly these rows, each as its text */
async function expectRows(expected: string[]) {
  await waitFor(() => {
    expect(
      within(screen.getByRole('main'))
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual(expected)
  })
}

const ROWS = ['Back SquatLibrary', 'Bench PressLibrary', 'Zercher SquatYours']

describe('the exercises list', () => {
  it('shows the library’s exercises and the user’s own', async () => {
    const requests = answerExercises()
    renderApp('/exercises', loggedInAs())

    await expectRows(ROWS)
    expect(screen.getByRole('heading', { level: 1, name: 'Exercises' })).toBeInTheDocument()
    expect(requests).toEqual([''])
  })

  it('opens from the Routines tab, which stays current', async () => {
    answerExercises()
    const { router } = renderApp('/routines', loggedInAs())

    await userEvent.click(await screen.findByRole('link', { name: 'Exercises' }))

    await expectRows(ROWS)
    expect(router.state.location.pathname).toBe('/exercises')
    expect(document.title).toBe('Exercises · Strength Journal')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { current: 'page' })).toHaveTextContent('Routines')
  })

  it('says when there are no exercises', async () => {
    answerExercises([])
    renderApp('/exercises', loggedInAs())

    expect(await screen.findByText('No exercises yet')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).queryByRole('list')).not.toBeInTheDocument()
  })

  it('says when the list didn’t load, and tries again', async () => {
    server.use(
      http.get('/api/exercises', () =>
        HttpResponse.json({ detail: 'Something broke', code: 'http_error' }, { status: 500 }),
      ),
    )
    renderApp('/exercises', loggedInAs())

    expect(await screen.findByRole('alert')).toHaveTextContent('Something broke')

    answerExercises()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await expectRows(ROWS)
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

    await expectRows(ROWS)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
