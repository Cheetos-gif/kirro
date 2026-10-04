'use client';

import { useActionState, useState } from 'react';

import { declareAction, type ActionState } from '@/app/actions';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useActionToast } from '@/hooks/use-action-toast';
import { formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

export function DeclareForm({
  releaseId,
  slots,
  disabled = false,
}: {
  releaseId: string;
  slots: Slot[];
  disabled?: boolean;
}) {
  const [state, action, pending] = useActionState<ActionState, FormData>(declareAction, null);
  useActionToast(state);
  const [groupSize, setGroupSize] = useState(2);
  const [maxPriceRupees, setMaxPriceRupees] = useState(300);
  const [selectedSlots, setSelectedSlots] = useState<string[]>(() => slots.map(slot => slot.slot_id));
  const reservePaise = Math.max(groupSize, 0) * Math.max(maxPriceRupees, 0) * 100;

  // The mock refuses a bid whose ceiling cannot reach the cheapest slot the caller accepted (#35), so
  // the form says the same thing first rather than letting the submit fail one hop away. Measured
  // against the *selected* slots, matching the server rule: only wanting the dear slot is fine.
  function toggleSlot(slotId: string) {
    setSelectedSlots(previous =>
      previous.includes(slotId) ? previous.filter(id => id !== slotId) : [...previous, slotId]
    );
  }

  const selectedPrices = slots
    .filter(slot => selectedSlots.includes(slot.slot_id))
    .map(slot => slot.price_per_person_paise);
  const cheapestSelectedRupees =
    selectedPrices.length === 0 ? null : Math.ceil(Math.min(...selectedPrices) / 100);
  const noSlots = selectedSlots.length === 0;
  const ceilingTooLow = cheapestSelectedRupees !== null && maxPriceRupees < cheapestSelectedRupees;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-sm font-medium">Enter the draw</p>
        <p className="text-sm text-muted-foreground">
          When you enter doesn&apos;t matter. If you won recently, your odds this time are slightly
          worse &mdash; see the draw explanation above.
        </p>
      </div>
      <form action={action} className="flex flex-col gap-4">
        <input type="hidden" name="release_id" value={releaseId} />

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">Slots you would take</legend>
          {slots.map(slot => (
            <Label key={slot.slot_id} className="flex items-center gap-2 font-normal">
              <Checkbox
                name="slot_ids"
                value={slot.slot_id}
                checked={selectedSlots.includes(slot.slot_id)}
                onCheckedChange={() => toggleSlot(slot.slot_id)}
              />
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
              value={groupSize}
              onChange={event => setGroupSize(Number(event.target.value) || 0)}
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
              min={cheapestSelectedRupees ?? 1}
              value={maxPriceRupees}
              onChange={event => setMaxPriceRupees(Number(event.target.value) || 0)}
              required
            />
          </div>
        </div>

        {noSlots ? (
          <p role="status" className="text-sm text-destructive">
            Pick at least one slot you would take.
          </p>
        ) : ceilingTooLow ? (
          <p role="status" className="text-sm text-destructive">
            Your maximum is below the cheapest slot you picked ({formatPaise(Math.min(...selectedPrices))}),
            so this bid could not win. Raise it or pick a cheaper slot.
          </p>
        ) : null}

        <p className="text-xs text-muted-foreground">
          We&apos;ll reserve {formatPaise(reservePaise)} now (people &times; your max) as a
          temporary payment hold (a mock Pine Labs hold for this demo). If you lose, it&apos;s
          released, not charged. The result comes to your WhatsApp number from{' '}
          <span className="text-foreground">settings</span>.
        </p>

        <Button
          type="submit"
          disabled={pending || disabled || noSlots || ceilingTooLow}
          className="w-fit"
        >
          {pending ? 'Entering...' : 'Enter the draw'}
        </Button>
      </form>
    </div>
  );
}
