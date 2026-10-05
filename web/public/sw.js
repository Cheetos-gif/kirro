// KIRRO's service worker. Hand-written rather than generated: the portal is server-rendered per
// request against live mock state (bookings, draws, prices), so caching whole pages would show
// stale data — the only thing worth caching offline is the static app shell (JS/CSS bundles,
// fonts, icons), never a page response itself. Scope is "/", registered from
// `src/components/pwa/service-worker-register.tsx`.

const CACHE_NAME = 'kirro-shell-v1';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches
      .keys()
      .then(names =>
        Promise.all(names.filter(name => name !== CACHE_NAME).map(name => caches.delete(name)))
      )
      .then(() => self.clients.claim())
  );
});

// Cache-first for Next's hashed static assets (safe: the filename changes when the content does);
// network-first, falling back to cache, for everything else. Never caches a navigation response,
// so a page always reflects live mock state when online, and falls back to nothing (the browser's
// own offline page) rather than a stale booking list when it is not.
self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const isStaticAsset =
    url.pathname.startsWith('/_next/static/') || url.pathname.startsWith('/_next/image');

  if (isStaticAsset) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      })
    );
  }
});

// Web Push (#22-adjacent PWA work). Payload is JSON `{title, body, url}` — see
// web/src/lib/push/send.ts, the only place that ever sends one.
self.addEventListener('push', event => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    return;
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || 'KIRRO', {
      body: payload.body,
      icon: '/kirro-192.png',
      badge: '/kirro-192.png',
      data: { url: payload.url || '/' },
    })
  );
});

// Focuses an already-open KIRRO tab if one exists, navigating it to the notification's URL;
// otherwise opens a new one. Standard pattern for "clicking a push notification acts like a link".
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl =
    event.notification.data && event.notification.data.url ? event.notification.data.url : '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    })
  );
});
