import { onlineManager } from '@tanstack/react-query'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import type { ExerciseRead } from '@/api/generated/model'
import { answerExercises, exercise } from '@/test/exercises'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'
import { loggedInAs, testUser } from '@/test/session'

afterEach(() => {
  onlineManager.setOnline(true)
})

const DUPLICATE_NAME = 'You already have an exercise with this name'

/** Answers POST /api/exercises, recording each body and CSRF header. Unless `respond` is given,
 * it adds the exercise to `all` and answers 201, as the API would */
function answerCreates(all: ExerciseRead[], respond?: () => Response) {
  const sent: { token: string | null; body: unknown }[] = []
  server.use(
    http.post('/api/exercises', async ({ request }) => {
      const body = (await request.json()) as { name: string }
      sent.push({ token: request.headers.get('X-CSRF-Token'), body })
      if (respond) return respond()
      const created = exercise(body.name.trim())
      all.push(created)
      all.sort((a, b) => a.name.localeCompare(b.name))
      return HttpResponse.json(created, { status: 201 })
    }),
  )
  return sent
}

/** Opens the form from the Exercises list, which shows `all` */
async function openForm(all: ExerciseRead[] = []) {
  answerExercises(all)
  const rendered = renderApp('/exercises', loggedInAs(testUser, 'the-token'))
  await userEvent.click(await screen.findByRole('button', { name: 'New exercise' }))
  return rendered
}

const nameField = () => screen.getByLabelText('Name')
const newButton = () => screen.getByRole('button', { name: 'New exercise' })

async function add(name: string) {
  await userEvent.type(nameField(), name)
  await userEvent.click(screen.getByRole('button', { name: 'Add exercise' }))
}

describe('the new exercise form', () => {
  it('adds an exercise, which shows in the list', async () => {
    const all = [exercise('Back Squat', { library: true })]
    const sent = answerCreates(all)
    await openForm(all)
    expect(nameField()).toHaveFocus()
    expect(newButton()).toHaveAttribute('aria-expanded', 'true')

    await add('Zercher Squat')

    expect(await screen.findByRole('status')).toHaveTextContent('Added “Zercher Squat”')
    expect(sent).toEqual([{ token: 'the-token', body: { name: 'Zercher Squat' } }])
    await waitFor(() => {
      expect(
        within(screen.getByRole('tabpanel'))
          .getAllByRole('listitem')
          .map((row) => row.textContent),
      ).toEqual(['Back SquatLibrary', 'Zercher SquatYours'])
    })
    // The form closes, and focus goes back to the button that opened it
    expect(screen.queryByRole('form', { name: 'New exercise' })).not.toBeInTheDocument()
    expect(newButton()).toHaveFocus()
    expect(newButton()).toHaveAttribute('aria-expanded', 'false')
  })

  it('puts a duplicate name on the name field, and stays open', async () => {
    const sent = answerCreates([], () =>
      HttpResponse.json({ detail: DUPLICATE_NAME, code: 'duplicate_name' }, { status: 409 }),
    )
    await openForm()

    await add('Back Squat')

    expect(await screen.findByText(DUPLICATE_NAME)).toBeInTheDocument()
    expect(nameField()).toHaveAttribute('aria-invalid', 'true')
    expect(nameField()).toHaveAccessibleDescription(DUPLICATE_NAME)
    expect(nameField()).toHaveValue('Back Squat')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(sent).toHaveLength(1)
  })

  it('needs a name, checked before sending', async () => {
    const sent = answerCreates([])
    await openForm()

    await add('   ')

    expect(await screen.findByText('Enter a name')).toBeInTheDocument()
    expect(nameField()).toHaveAttribute('aria-invalid', 'true')
    expect(sent).toEqual([])
  })

  it('says so at once when the browser is offline', async () => {
    answerCreates([], () => HttpResponse.error())
    await openForm()
    act(() => {
      onlineManager.setOnline(false)
    })

    await add('Zercher Squat')

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
    expect(nameField()).toHaveValue('Zercher Squat')
  })

  it('closes without adding on Cancel', async () => {
    const sent = answerCreates([])
    await openForm()

    await userEvent.type(nameField(), 'Zercher Squat')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('form', { name: 'New exercise' })).not.toBeInTheDocument()
    expect(newButton()).toHaveFocus()
    expect(sent).toEqual([])
  })
})
