import { Badge } from '@/components/ui/badge';

const DONE = new Set(['CONFIRMED', 'CLOSED']);
const STOPPED = new Set(['CANCELLED', 'RELEASED', 'FAILED', 'EXPIRED', 'UNALLOCATED']);

/** Colours a declaration state consistently wherever it appears (list, detail). */
export function StateBadge({ state }: { state: string }) {
  const variant = DONE.has(state) ? 'default' : STOPPED.has(state) ? 'destructive' : 'secondary';
  return <Badge variant={variant}>{state}</Badge>;
}
