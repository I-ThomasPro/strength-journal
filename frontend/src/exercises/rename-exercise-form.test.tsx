import { onlineManager } from '@tanstack/react-query'
import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
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
const READ_ONLY = 'Library items can’t be changed'

/** Answers PATCH /api/exercises/:id, recording each id, body and CSRF header. Unless `respond`
 * is given, it renames the exercise in `all` and answers with it, as the API would */
function answerRenames(all: ExerciseRead[], respond?: () => Response) {
  const sent: { id: unknown; token: string | null; body: unknown }[] = []
  server.use(
    http.patch('/api/exercises/:id', async ({ params, request }) => {
      const body = (await request.json()) as { name: string }
      sent.push({ id: params.id, token: request.headers.get('X-CSRF-Token'), body })
      if (respond) return respond()
      const found = all.find((item) => item.id === params.id)
      if (!found) return new HttpResponse(null, { status: 404 })
      found.name = body.name.trim()
      return HttpResponse.json(found)
    }),
  )
  return sent
}

function exercises() {
  return [exercise('Back Squat', { library: true }), exercise('Zercher Squat')]
}

/** Opens the exercise's page from the list, which shows `all`, then its rename form */
async function openRenameForm(all: ExerciseRead[]) {
  answerExercises(all)
  const rendered = renderApp('/exercises', loggedInAs(testUser, 'the-token'))
  await userEvent.click(await screen.findByRole('link', { name: /Zercher Squat/ }))
  await userEvent.click(await screen.findByRole('button', { name: 'Rename' }))
  return rendered
}

const nameField = () => screen.getByLabelText('Name')
const renameButton = () => screen.getByRole('button', { name: 'Rename' })
const saveButton = () => screen.getByRole('button', { name: 'Save' })

async function renameTo(name: string) {
  await userEvent.clear(nameField())
  await userEvent.type(nameField(), name)
  await userEvent.click(saveButton())
}

describe('the rename exercise form', () => {
  it('renames an exercise, on its page and in the list', async () => {
    const all = exercises()
    const sent = answerRenames(all)
    await openRenameForm(all)
    expect(nameField()).toHaveValue('Zercher Squat')
    expect(nameField()).toHaveFocus()
    // Nothing to save until the name changes
    expect(saveButton()).toBeDisabled()

    await renameTo('Zercher Carry')

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Zercher Carry' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Renamed')
    expect(sent).toEqual([
      { id: 'id-zercher-squat', token: 'the-token', body: { name: 'Zercher Carry' } },
    ])
    // The form closes, and focus goes back to the button that opened it
    expect(screen.queryByRole('form', { name: 'Rename exercise' })).not.toBeInTheDocument()
    expect(renameButton()).toHaveFocus()

    // The list it was opened from loads afresh, however slowly, without showing the old name
    server.use(
      http.get('/api/exercises', async () => {
        await delay(50)
        return HttpResponse.json({ items: all, total: all.length })
      }),
    )
    await userEvent.click(screen.getByRole('link', { name: 'Exercises' }))
    expect(screen.getByText('Loading exercises…')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Zercher Squat/ })).not.toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Zercher Carry/ })).toBeInTheDocument()
  })

  it('puts a duplicate name on the name field, and stays open', async () => {
    const all = exercises()
    answerRenames(all, () =>
      HttpResponse.json({ detail: DUPLICATE_NAME, code: 'duplicate_name' }, { status: 409 }),
    )
    await openRenameForm(all)

    await renameTo('Sled Push')

    expect(await screen.findByText(DUPLICATE_NAME)).toBeInTheDocument()
    expect(nameField()).toHaveAttribute('aria-invalid', 'true')
    expect(nameField()).toHaveAccessibleDescription(DUPLICATE_NAME)
    expect(screen.getByRole('heading', { level: 2, name: 'Zercher Squat' })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says so when the API refuses, as it does for a library exercise', async () => {
    const all = exercises()
    answerRenames(all, () =>
      HttpResponse.json({ detail: READ_ONLY, code: 'read_only' }, { status: 403 }),
    )
    await openRenameForm(all)

    await renameTo('Zercher Carry')

    expect(await screen.findByRole('alert')).toHaveTextContent(READ_ONLY)
    expect(screen.getByRole('heading', { level: 2, name: 'Zercher Squat' })).toBeInTheDocument()
  })

  it('isn’t offered for a library exercise', async () => {
    answerExercises(exercises())
    renderApp('/exercises/id-back-squat', loggedInAs())

    expect(await screen.findByText('Library exercise')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
  })

  it('says so at once when the browser is offline', async () => {
    const all = exercises()
    answerRenames(all, () => HttpResponse.error())
    await openRenameForm(all)
    act(() => {
      onlineManager.setOnline(false)
    })

    await renameTo('Zercher Carry')

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t reach the server')
    expect(nameField()).toHaveValue('Zercher Carry')
  })

  it('closes without renaming on Cancel', async () => {
    const all = exercises()
    const sent = answerRenames(all)
    await openRenameForm(all)

    await userEvent.type(nameField(), ' Carry')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('form', { name: 'Rename exercise' })).not.toBeInTheDocument()
    expect(renameButton()).toHaveFocus()
    expect(screen.getByRole('heading', { level: 2, name: 'Zercher Squat' })).toBeInTheDocument()
    expect(sent).toEqual([])
  })
})
