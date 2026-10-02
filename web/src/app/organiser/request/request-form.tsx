'use client';

import { useActionState } from 'react';

import { requestOrganiserAction, type ActionState } from '@/app/actions';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function RequestOrganiserForm({ defaultName }: { defaultName?: string }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(
    requestOrganiserAction,
    null
  );

  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="org-name">Organiser name</Label>
        <Input id="org-name" name="name" defaultValue={defaultName} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="org-contact">Contact</Label>
        <Input id="org-contact" name="contact" placeholder="Phone or email" required />
      </div>
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? 'Submitting…' : 'Request organiser access'}
      </Button>
      {state ? (
        <Alert variant={state.ok ? 'default' : 'destructive'}>
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      ) : null}
    </form>
  );
}
