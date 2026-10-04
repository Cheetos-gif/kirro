'use client';

import { useActionState } from 'react';

import { buyAction, type ActionState } from '@/app/actions';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useActionToast } from '@/hooks/use-action-toast';
import { formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

export function BuyForm({ releaseId, slots }: { releaseId: string; slots: Slot[] }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(buyAction, null);
  useActionToast(state);
  // Preselect the first slot that actually has seats, so the common case needs no interaction.
  const firstAvailable = slots.find(slot => slot.capacity > 0)?.slot_id;

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
            <Select name="slot_id" required defaultValue={firstAvailable}>
              <SelectTrigger id={`slot-${releaseId}`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {slots.map(slot => (
                  <SelectItem key={slot.slot_id} value={slot.slot_id} disabled={slot.capacity < 1}>
                    {slot.label}, {formatPaise(slot.price_per_person_paise)}, {slot.capacity} left
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
