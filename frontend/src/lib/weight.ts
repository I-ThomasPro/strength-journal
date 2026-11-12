// Weights travel as decimal strings with two places ("102.50"), as the API sends them, so
// they're never rounded by floating point. These convert them for people to read and type

import type { WeightUnit } from '@/api/generated/model'

// Up to 4 digits, then up to 2 decimals after a point or comma: 0 to 9999.99, the API's range
const WEIGHT_INPUT = /^(\d{0,4})(?:[.,](\d{0,2}))?$/

/** A typed weight in the API's format ("102.5" or "102,5" → "102.50"), or null if it isn't a
 * weight the API accepts */
export function parseWeight(input: string): string | null {
  const match = WEIGHT_INPUT.exec(input.trim())
  if (!match) return null
  const [, whole = '', fraction = ''] = match
  if (whole === '' && fraction === '') return null
  return `${String(Number(whole))}.${fraction.padEnd(2, '0')}`
}

/** A weight for display, without trailing zeros ("102.50" → "102.5", "100.00" → "100"),
 * followed by its unit when given */
export function formatWeight(weight: string, unit?: WeightUnit): string {
  const [whole = '0', fraction = ''] = weight.split('.')
  const decimals = fraction.replace(/0+$/, '')
  const number = decimals === '' ? whole : `${whole}.${decimals}`
  return unit === undefined ? number : `${number} ${unit}`
}
