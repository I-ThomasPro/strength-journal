import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { App } from '@/app'

it('opens on the Train tab', async () => {
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Train' })).toBeInTheDocument()
  expect(window.location.pathname).toBe('/train')
})
