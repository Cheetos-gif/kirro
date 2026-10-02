'use client';

import { useActionState } from 'react';

import { buyAction, type ActionState } from '@/app/actions';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

export function BuyForm({ releaseId, slots }: { releaseId: string; slots: Slot[] }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(buyAction, null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Buy now</CardTitle>
        <CardDescription>
          First come, first served: this holds the seats, charges, and confirms in one step. No draw
          is involved.
        </CardDescription>
      </CardHeader>
      <CardContent>
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
                    {slot.label} · {formatPaise(slot.price_per_person_paise)} · {slot.capacity} left
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`qty-${releaseId}`}>Quantity</Label>
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

          <Button type="submit" disabled={pending}>
            {pending ? 'Booking…' : 'Buy'}
          </Button>

          {state ? (
            <Alert variant={state.ok ? 'default' : 'destructive'}>
              <AlertDescription>{state.message}</AlertDescription>
            </Alert>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
