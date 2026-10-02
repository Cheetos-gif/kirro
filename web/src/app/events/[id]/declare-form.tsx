'use client';

import { useActionState } from 'react';

import { declareAction, type ActionState } from '@/app/actions';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

export function DeclareForm({ releaseId, slots }: { releaseId: string; slots: Slot[] }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(declareAction, null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Join the draw</CardTitle>
        <CardDescription>
          Say what you would accept. The draw runs once the window closes and treats everyone the
          same, so there is no rush.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form action={action} className="flex flex-col gap-4">
          <input type="hidden" name="release_id" value={releaseId} />

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">Slots you would take</legend>
            {slots.map(slot => (
              <Label key={slot.slot_id} className="flex items-center gap-2 font-normal">
                <Checkbox name="slot_ids" value={slot.slot_id} defaultChecked />
                <span>
                  {slot.label}, {formatPaise(slot.price_per_person_paise)}
                </span>
              </Label>
            ))}
          </fieldset>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`group-${releaseId}`}>People</Label>
              <Input
                id={`group-${releaseId}`}
                name="group_size"
                type="number"
                min={1}
                defaultValue={2}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`min-group-${releaseId}`}>Fewest people</Label>
              <Input
                id={`min-group-${releaseId}`}
                name="min_group_size"
                type="number"
                min={1}
                defaultValue={2}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`ceiling-${releaseId}`}>Most you will pay each (₹)</Label>
              <Input
                id={`ceiling-${releaseId}`}
                name="max_price_rupees"
                type="number"
                min={1}
                defaultValue={300}
                required
              />
            </div>
          </div>

          <Button type="submit" disabled={pending}>
            {pending ? 'Joining...' : 'Join the draw'}
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
