'use client';

import { useActionState } from 'react';

import { createQuickDemoAction, type ActionState } from '@/app/actions';
import { Button } from '@/components/ui/button';

/**
 * One click seeds a random, immediately-open event and drops the caller on the voice channel to book
 * it (#32) — the demo's point is the agent, not event setup.
 *
 * The action redirects on success; the only thing to show here is a failure.
 */
export function QuickDemoButton() {
  const [state, action, pending] = useActionState<ActionState, FormData>(
    createQuickDemoAction,
    null
  );

  return (
    <form action={action} className="flex flex-col gap-2">
      <Button type="submit" variant="outline" size="sm" className="w-fit" disabled={pending}>
        {pending ? 'Organising…' : 'Organise a demo event'}
      </Button>
      {state && !state.ok ? <p className="text-sm text-destructive">{state.message}</p> : null}
    </form>
  );
}
