import { describe, expect, it } from 'vitest'

import { formatWeight, parseWeight } from '@/lib/weight'

describe('parseWeight', () => {
  it.each([
    ['100', '100.00'],
    ['102.5', '102.50'],
    ['102,5', '102.50'],
    ['102.55', '102.55'],
    [' 60 ', '60.00'],
    ['.5', '0.50'],
    ['5.', '5.00'],
    ['0', '0.00'],
    ['007.5', '7.50'],
    ['9999.99', '9999.99'],
  ])('reads %j as %j', (input, expected) => {
    expect(parseWeight(input)).toBe(expected)
  })

  it.each(['', ' ', '.', 'abc', '-5', '1e3', '102.555', '10000', '1.2.3', '1,000.5'])(
    'rejects %j',
    (input) => {
      expect(parseWeight(input)).toBeNull()
    },
  )
})

describe('formatWeight', () => {
  it.each([
    ['100.00', '100'],
    ['102.50', '102.5'],
    ['102.55', '102.55'],
    ['0.00', '0'],
    ['60', '60'],
  ])('shows %j as %j', (weight, expected) => {
    expect(formatWeight(weight)).toBe(expected)
  })

  it('adds the unit when given', () => {
    expect(formatWeight('102.50', 'kg')).toBe('102.5 kg')
    expect(formatWeight('225.00', 'lb')).toBe('225 lb')
  })
})
