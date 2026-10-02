'use client';

import { useActionState } from 'react';

import { buyAction, type ActionState } from '@/app/actions';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useActionToast } from '@/hooks/use-action-toast';
import { formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

export function BuyForm({ releaseId, slots }: { releaseId: string; slots: Slot[] }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(buyAction, null);
  useActionToast(state);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-sm font-medium">Buy now</p>
        <p className="text-sm text-muted-foreground">
          First come, first served. Payment is taken immediately.
        </p>
      </div>
      <form action={action} className="flex flex-col gap-4">
        <input type="hidden" name="release_id" value={releaseId} />

        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`slot-${releaseId}`}>Slot</Label>
            {/* Native select: it submits its value with the form unconditionally. */}
            <select
              id={`slot-${releaseId}`}
              name="slot_id"
              required
              className="h-9 w-full rounded-3xl border border-transparent bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
            >
              {slots.map(slot => (
                <option key={slot.slot_id} value={slot.slot_id} disabled={slot.capacity < 1}>
                  {slot.label}, {formatPaise(slot.price_per_person_paise)}, {slot.capacity} left
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`qty-${releaseId}`}>How many</Label>
            <Input
              id={`qty-${releaseId}`}
              name="quantity"
              type="number"
              min={1}
              defaultValue={1}
              className="sm:w-24"
              required
            />
          </div>
        </div>

        <Button type="submit" disabled={pending} className="w-fit">
          {pending ? 'Buying...' : 'Buy'}
        </Button>
      </form>
    </div>
  );
}
