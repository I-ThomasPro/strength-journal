import { describe, expect, it } from 'vitest'

import { safeNext } from '@/auth/next-path'

const origin = 'https://app.example'

describe('safeNext', () => {
  it.each([
    ['/history', '/history'],
    ['/history?week=2#today', '/history?week=2#today'],
    ['/routines/./abc', '/routines/abc'],
  ])('keeps the path %j', (next, expected) => {
    expect(safeNext(next, origin)).toBe(expected)
  })

  it.each([
    null,
    '',
    'history',
    '//evil.example/path',
    '/\\evil.example',
    '/\t/evil.example',
    'https://evil.example/history',
    'https://app.example/history',
    'javascript:alert(1)',
  ])('rejects %j', (next) => {
    expect(safeNext(next, origin)).toBeNull()
  })
})
