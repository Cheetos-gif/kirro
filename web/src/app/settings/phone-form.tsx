'use client';

import { useActionState } from 'react';

import { savePhoneAction, type ActionState } from '@/app/actions';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useActionToast } from '@/hooks/use-action-toast';

export function PhoneSettingsForm({ defaultPhone }: { defaultPhone?: string }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(savePhoneAction, null);
  useActionToast(state);

  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="flex max-w-sm flex-col gap-1.5">
        <Label htmlFor="notify_phone">WhatsApp number</Label>
        <Input
          id="notify_phone"
          name="notify_phone"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          defaultValue={defaultPhone}
          placeholder="+919876543210"
          required
        />
        <p className="text-xs text-muted-foreground">
          Include the country code. Every draw result for you goes here, so you only set it once.
        </p>
      </div>
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? 'Saving...' : 'Save number'}
      </Button>
    </form>
  );
}
