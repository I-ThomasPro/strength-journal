import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { App } from '@/app'
import { server } from '@/test/server'
import { loggedOut } from '@/test/session'

it('opens on the Train tab', async () => {
  server.use(loggedOut())
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Train' })).toBeInTheDocument()
  expect(window.location.pathname).toBe('/train')
})
