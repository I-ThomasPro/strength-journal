import { onlineManager } from '@tanstack/react-query'
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { answerExercises, exercise } from '@/test/exercises'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs } from '@/test/session'

afterEach(() => {
  onlineManager.setOnline(true)
})

const backSquat = exercise('Back Squat', { library: true })
const zercherSquat = exercise('Zercher Squat')
const EXERCISES = [backSquat, zercherSquat]

const MISSING = 'This exercise doesn’t exist. It may have been deleted.'

/** Answers GET /api/exercises/:id with an error */
function failToShow(status: number, code: string) {
  server.use(
    http.get('/api/exercises/:id', () =>
      HttpResponse.json({ detail: 'Something broke', code }, { status }),
    ),
  )
}

describe('an exercise’s page', () => {
  it('shows a library exercise', async () => {
    answerExercises(EXERCISES)
    renderApp(`/exercises/${backSquat.id}`, loggedInAs())

    expect(await screen.findByRole('heading', { level: 2, name: 'Back Squat' })).toBeInTheDocument()
    expect(screen.getByText('Library exercise')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Exercise' })).toBeInTheDocument()
    expect(document.title).toBe('Exercise · Strength Journal')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { current: 'page' })).toHaveTextContent('Routines')
    // Opened by its address, it links back to the plain list
    expect(screen.getByRole('link', { name: 'Exercises' })).toHaveAttribute('href', '/exercises')
  })

  it('shows one of the user’s own', async () => {
    answerExercises(EXERCISES)
    renderApp(`/exercises/${zercherSquat.id}`, loggedInAs())

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Zercher Squat' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Your exercise')).toBeInTheDocument()
  })

  it('opens from the list, and goes back to the same tab and search', async () => {
    answerExercises(EXERCISES)
    const { router } = renderApp('/exercises?scope=mine&q=squat', loggedInAs())

    await userEvent.click(await screen.findByRole('link', { name: /Zercher Squat/ }))

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Zercher Squat' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(`/exercises/${zercherSquat.id}`)

    await userEvent.click(screen.getByRole('link', { name: 'Exercises' }))

    expect(await screen.findByRole('link', { name: /Zercher Squat/ })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/exercises')
    expect(router.state.location.search).toBe('?scope=mine&q=squat')
    expect(screen.getByRole('searchbox', { name: 'Search exercises' })).toHaveValue('squat')
    expect(screen.getByRole('tab', { name: 'Mine' })).toHaveAttribute('aria-selected', 'true')
  })

  it.each([
    ['isn’t there, or is someone else’s', 404, 'not_found'],
    ['has an address that isn’t an exercise’s', 422, 'invalid'],
  ])('says so when the exercise %s', async (_, status, code) => {
    failToShow(status, code)
    renderApp('/exercises/nothing-here', loggedInAs())

    expect(await screen.findByText(MISSING)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Exercises' })).toHaveAttribute('href', '/exercises')
  })

  it('says when it didn’t load, and tries again', async () => {
    failToShow(500, 'http_error')
    renderApp(`/exercises/${zercherSquat.id}`, loggedInAs())

    expect(await screen.findByRole('alert')).toHaveTextContent('Something broke')

    answerExercises(EXERCISES)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Zercher Squat' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('says it needs a connection while offline, then loads', async () => {
    answerExercises(EXERCISES)
    // The list is already open when the connection drops
    renderApp('/exercises', loggedInAs())
    const row = await screen.findByRole('link', { name: /Zercher Squat/ })
    act(() => {
      onlineManager.setOnline(false)
    })
    await userEvent.click(row)

    expect(await screen.findByRole('status')).toHaveTextContent(
      'You’re offline. Exercises need a connection.',
    )
    expect(screen.queryByText('Loading exercise…')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument()

    act(() => {
      onlineManager.setOnline(true)
    })

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Zercher Squat' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
