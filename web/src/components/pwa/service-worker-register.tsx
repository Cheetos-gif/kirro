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

    // Registered after `load`, not on mount: a service-worker registration competes for the
    // browser's network/CPU budget with whatever the page is still fetching, and nothing here is
    // needed before first paint. If the page has already finished loading by the time this effect
    // runs, `load` has already fired and this registers on the next tick instead.
    const register = () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Best-effort: a failed registration should not break the rest of the page.
      });
    };

    if (document.readyState === 'complete') {
      register();
      return;
    }
    window.addEventListener('load', register, { once: true });
    return () => window.removeEventListener('load', register);
  }, []);

  return null;
}
