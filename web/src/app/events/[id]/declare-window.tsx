'use client';

import { useSyncExternalStore } from 'react';

import type { Slot } from '@/lib/kirro/schemas';

import { DeclareForm } from './declare-form';

function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * A once-a-second clock as an external store, so React re-renders the countdown without an effect
 * calling setState. `getServerSnapshot` returns null, which is what keeps hydration honest: the
 * server has no client clock, so both the server render and the first client render agree on "not
 * measured yet", and the countdown only appears once the store is live.
 */
let tick: number | null = null;
const listeners = new Set<() => void>();

function subscribeToClock(onChange: () => void): () => void {
  if (tick === null) tick = Date.now();
  listeners.add(onChange);
  onChange();
  const timer = window.setInterval(() => {
    tick = Date.now();
    for (const listener of listeners) listener();
  }, 1000);
  return () => {
    window.clearInterval(timer);
    listeners.delete(onChange);
  };
}

function useClock(): number | null {
  return useSyncExternalStore(
    subscribeToClock,
    () => tick,
    () => null
  );
}

/**
 * The fair-draw declare window, with a live countdown (#32). A release may not open immediately —
 * `declare_window_starts_at` (set by the near-future demo action) pushes the start forward — so the
 * form stays disabled until the browser's own clock says the window is open, rather than trusting
 * the server-computed `declarations_open` that was only true when the page was rendered.
 */
export function DeclareWindow({
  releaseId,
  slots,
  startsAt,
  opensAt,
}: {
  releaseId: string;
  slots: Slot[];
  startsAt?: string | null;
  opensAt: string;
}) {
  const now = useClock();

  const startMs = startsAt ? Date.parse(startsAt) : null;
  const endMs = Date.parse(opensAt);
  // Until the client clock exists, only an open-from-creation release (no scheduled start) is
  // treated as open; anything else waits for the first tick.
  const open = now === null ? startMs === null : (startMs === null || now >= startMs) && now < endMs;

  let status: string;
  if (now === null) {
    status = 'Checking the declare window…';
  } else if (startMs !== null && now < startMs) {
    status = `Opens in ${formatRemaining(startMs - now)}`;
  } else if (now < endMs) {
    status = `Closes in ${formatRemaining(endMs - now)}`;
  } else {
    status = 'Window closed — the draw runs within 5 minutes.';
  }

  return (
    <div className="flex flex-col gap-3">
      <p
        role="status"
        className="w-fit rounded-full border border-border px-3 py-1 font-mono text-xs tracking-wide text-muted-foreground uppercase"
      >
        {status}
      </p>
      <DeclareForm releaseId={releaseId} slots={slots} disabled={!open} />
    </div>
  );
}
