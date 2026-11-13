import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'

/** The Routines tab. The routines themselves come with #58; until then it leads to the
 * exercises */
export function RoutinesPage() {
  return (
    <div className="space-y-6">
      <Link
        to="/exercises"
        className="flex items-center justify-between rounded-md border px-4 py-3 font-medium outline-none hover:bg-accent focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        Exercises
        <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground" />
      </Link>

      <p className="text-muted-foreground">Routines are coming soon</p>
    </div>
  )
}
