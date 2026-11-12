import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-muted-foreground">There’s nothing at this address.</p>
      <Button asChild>
        <Link to="/train">Go to Train</Link>
      </Button>
    </section>
  )
}
