'use client';

import { useEffect } from 'react';

/**
 * Registers `/sw.js` once the page has loaded. Mounted once in the root layout. Silently does
 * nothing in a browser without `serviceWorker` support (or in dev tooling that doesn't run a real
 * browser) — a PWA degrades to a plain web page there, not an error.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Best-effort: a failed registration should not break the rest of the page.
    });
  }, []);

  return null;
}
