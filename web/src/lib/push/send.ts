import webpush, { WebPushError } from 'web-push';

import { isApiError } from '@/api';
import { env } from '@/env';
import * as api from '@/lib/kirro/api';

/** True once VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY are both set. Blank (the default) disables every
 * push code path rather than throwing, matching MOCK_ADMIN_KEY's and the Pine Labs call-out's
 * "unset is a no-op" convention. */
export function pushEnabled(): boolean {
  return Boolean(env.VAPID_PUBLIC_KEY && env.VAPID_PRIVATE_KEY);
}

let configured = false;
function ensureConfigured() {
  if (configured || !pushEnabled()) return;
  webpush.setVapidDetails(env.VAPID_SUBJECT, env.VAPID_PUBLIC_KEY, env.VAPID_PRIVATE_KEY);
  configured = true;
}

export type PushPayload = { title: string; body: string; url?: string };

/**
 * Sends a real Web Push notification to `userContact`'s stored subscription, if any. Best-effort:
 * never throws into a caller's booking/declare flow — a push failure must not undo or mask a real
 * reservation. A `404`/`410` from the push service means the subscription expired or was revoked
 * (the browser unsubscribed on its own); that is cleaned up here so a stale subscription does not
 * keep failing silently forever.
 */
export async function sendPushNotification(
  userContact: string,
  payload: PushPayload
): Promise<void> {
  if (!pushEnabled()) return;
  ensureConfigured();

  let subscription;
  try {
    subscription = (await api.getUserProfile(userContact)).push_subscription;
  } catch {
    return;
  }
  if (!subscription) return;

  try {
    await webpush.sendNotification(subscription, JSON.stringify(payload));
  } catch (error) {
    if (error instanceof WebPushError && (error.statusCode === 404 || error.statusCode === 410)) {
      try {
        await api.setUserProfile(userContact, { push_subscription: null });
      } catch (cleanupError) {
        if (!isApiError(cleanupError)) throw cleanupError;
      }
    }
    // Any other failure (network, malformed payload) is swallowed deliberately: push is a
    // best-effort notification channel, not part of the booking's own success/failure contract.
  }
}
