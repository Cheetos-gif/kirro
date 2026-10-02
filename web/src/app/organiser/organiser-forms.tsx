'use client';

import { useActionState } from 'react';

import {
  createEventAction,
  createReleaseAction,
  setEventStatusAction,
  type ActionState,
} from '@/app/actions';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { KirroEvent } from '@/lib/kirro/schemas';

const SELECT_CLASS =
  'h-9 w-full rounded-3xl border border-transparent bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30';

function Result({ state }: { state: ActionState }) {
  if (!state) return null;
  return (
    <Alert variant={state.ok ? 'default' : 'destructive'}>
      <AlertDescription>{state.message}</AlertDescription>
    </Alert>
  );
}

export function CreateEventForm() {
  const [state, action, pending] = useActionState<ActionState, FormData>(createEventAction, null);

  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="event-name">Event name</Label>
        <Input id="event-name" name="name" required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="event-status">Status</Label>
        <select id="event-status" name="status" defaultValue="draft" className={SELECT_CLASS}>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
        </select>
      </div>
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? 'Creating...' : 'Create event'}
      </Button>
      <Result state={state} />
    </form>
  );
}

export function EventStatusForm({ event }: { event: KirroEvent }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(
    setEventStatusAction,
    null
  );
  const next = event.status === 'published' ? 'draft' : 'published';

  return (
    <form action={action} className="flex items-center gap-2">
      <input type="hidden" name="event_id" value={event.event_id} />
      <input type="hidden" name="status" value={next} />
      <Button type="submit" variant="outline" size="sm" disabled={pending}>
        {pending ? 'Saving...' : next === 'published' ? 'Publish' : 'Unpublish'}
      </Button>
      {state && !state.ok ? (
        <span className="text-xs text-destructive">{state.message}</span>
      ) : null}
    </form>
  );
}

export function CreateReleaseForm({ events }: { events: KirroEvent[] }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(createReleaseAction, null);

  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Create an event first, then add a release to it.
      </p>
    );
  }

  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-event">Event</Label>
          <select id="rel-event" name="event_id" required className={SELECT_CLASS}>
            {events.map(event => (
              <option key={event.event_id} value={event.event_id}>
                {event.name} ({event.status})
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-mode">How it sells</Label>
          <select
            id="rel-mode"
            name="allocation_mode"
            defaultValue="fair_draw"
            className={SELECT_CLASS}
          >
            <option value="fair_draw">Draw, for slots people compete for</option>
            <option value="instant_buy">Buy now, in order of arrival</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-date">Date</Label>
          <Input id="rel-date" name="date" type="date" required />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-opens">Opens</Label>
          <Input id="rel-opens" name="opens_at" type="datetime-local" required />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-label">Slot label</Label>
          <Input id="rel-label" name="label" placeholder="Court 1, 07:00 to 08:00" required />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-starts">Starts</Label>
          <Input id="rel-starts" name="starts_at" type="datetime-local" required />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-capacity">Seats</Label>
          <Input
            id="rel-capacity"
            name="capacity"
            type="number"
            min={1}
            defaultValue={8}
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rel-price">Price each (₹)</Label>
          <Input
            id="rel-price"
            name="price_rupees"
            type="number"
            min={1}
            defaultValue={250}
            required
          />
        </div>
      </div>
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? 'Creating...' : 'Create release'}
      </Button>
      <Result state={state} />
    </form>
  );
}
