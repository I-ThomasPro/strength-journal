import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground">There’s nothing at this address.</p>
      <Button asChild>
        <Link to="/train">Go to Train</Link>
      </Button>
    </div>
  )
}
