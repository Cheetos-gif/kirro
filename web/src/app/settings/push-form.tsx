'use client';

import { useEffect, useState, useTransition } from 'react';
import { toast } from 'sonner';

import type { ActionState } from '@/app/actions';
import { clearPushSubscriptionAction, savePushSubscriptionAction, sendTestPushAction } from '@/app/actions';
import { Button } from '@/components/ui/button';
import { pushSubscriptionSchema } from '@/lib/kirro/schemas';
import { currentPushSubscription, pushSupported, subscribeToPush } from '@/lib/push/subscribe';

/** `checking` while the initial device lookup is in flight, so the toggle never flashes the wrong state. */
type Status = 'checking' | 'unsupported' | 'disabled' | 'enabled';

/** Three call sites (enable/disable/test) need the same `ActionState -> toast` mapping. */
function toastResult(result: ActionState) {
  if (!result) return;
  if (result.ok) toast.success(result.message);
  else toast.error(result.message);
}

export function PushNotificationsForm() {
  const [status, setStatus] = useState<Status>(() => (pushSupported() ? 'checking' : 'unsupported'));
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!pushSupported()) return;
    currentPushSubscription()
      .then(subscription => setStatus(subscription ? 'enabled' : 'disabled'))
      .catch(() => setStatus('disabled'));
  }, []);

  function enable() {
    startTransition(async () => {
      try {
        const res = await fetch('/api/push/vapid-public-key');
        if (!res.ok) {
          const body = (await res.json()) as { error?: string };
          throw new Error(body.error ?? 'Push notifications are not configured.');
        }
        const { publicKey } = (await res.json()) as { publicKey: string };
        const subscription = await subscribeToPush(publicKey);
        const result = await savePushSubscriptionAction(pushSubscriptionSchema.parse(subscription.toJSON()));
        toastResult(result);
        setStatus(result?.ok ? 'enabled' : 'disabled');
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Could not enable notifications.');
      }
    });
  }

  function disable() {
    startTransition(async () => {
      try {
        const subscription = await currentPushSubscription();
        await subscription?.unsubscribe();
      } catch {
        // The server-side clear below still runs even if the browser's own unsubscribe fails.
      }
      const result = await clearPushSubscriptionAction();
      toastResult(result);
      setStatus('disabled');
    });
  }

  function sendTest() {
    startTransition(async () => {
      toastResult(await sendTestPushAction());
    });
  }

  if (status === 'unsupported') {
    return <p className="text-sm text-muted-foreground">Not supported on this browser.</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      {status === 'enabled' ? (
        <>
          <Button type="button" variant="outline" disabled={pending} onClick={disable}>
            {pending ? 'Working...' : 'Turn off'}
          </Button>
          <Button type="button" variant="ghost" disabled={pending} onClick={sendTest}>
            Send test notification
          </Button>
        </>
      ) : (
        <Button type="button" disabled={pending || status === 'checking'} onClick={enable}>
          {pending ? 'Working...' : 'Enable on this device'}
        </Button>
      )}
    </div>
  );
}
