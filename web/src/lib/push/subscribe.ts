/** A VAPID public key, as served by `GET /api/push/vapid-public-key`, is URL-safe base64; the
 * Push API's `applicationServerKey` wants it as raw bytes backed by a concrete `ArrayBuffer`
 * (not the wider `ArrayBufferLike` a plain `Uint8Array.from` produces under current lib types). */
function urlBase64ToBytes(base64Url: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

export function pushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

/** Current subscription for this browser/device, or `null` if never subscribed. Does not request
 * permission — safe to call on page load to decide what the settings toggle should show. */
export async function currentPushSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

/** Requests notification permission, subscribes this browser via the given VAPID public key, and
 * returns the subscription. Throws if permission is denied or the browser refuses — callers
 * should catch and show a message rather than let it crash the settings page. */
export async function subscribeToPush(vapidPublicKey: string): Promise<PushSubscription> {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('Notification permission was not granted.');
  }
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToBytes(vapidPublicKey),
  });
}
