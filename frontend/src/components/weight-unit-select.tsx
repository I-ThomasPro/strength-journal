import type { ComponentProps } from 'react'

import { WeightUnit } from '@/api/generated/model'
import { cn } from '@/lib/utils'

/** kg or lb: a native select styled like Input. Spread react-hook-form's `register()` into it */
export function WeightUnitSelect({ className, ...props }: ComponentProps<'select'>) {
  return (
    <select
      className={cn(
        'h-9 w-full rounded-md border border-input bg-transparent px-3 text-base shadow-xs outline-none md:text-sm',
        'focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50',
        className,
      )}
      {...props}
    >
      {Object.values(WeightUnit).map((unit) => (
        <option key={unit} value={unit}>
          {unit}
        </option>
      ))}
    </select>
  )
}
