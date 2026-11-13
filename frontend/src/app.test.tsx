import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { App } from '@/app'
import { server } from '@/test/server'
import { loggedInAs } from '@/test/session'

it('opens on the Train tab when logged in', async () => {
  server.use(loggedInAs())
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Train' })).toBeInTheDocument()
  expect(window.location.pathname).toBe('/train')
})
