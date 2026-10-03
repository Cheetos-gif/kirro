'use client';

import { useSyncExternalStore } from 'react';

import { formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

export type DemoPrompt = { name: string; opensAt: string; startsAt: string | null; slots: Slot[] };

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

function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, '0')}`;
}

/**
 * Names the event the "Organise a demo event" button just seeded, and says what to do with it: say
 * it out loud to the agent. The window opens within seconds, so this is mostly a "start talking"
 * nudge; the countdown exists so a caller who races ahead is told to wait rather than left guessing
 * why the agent refused the declaration (#32).
 */
export function DemoPromptCard({ demo }: { demo: DemoPrompt }) {
  const now = useClock();

  const startMs = demo.startsAt ? Date.parse(demo.startsAt) : null;
  const endMs = Date.parse(demo.opensAt);

  let timing: string | null = null;
  if (now !== null) {
    if (startMs !== null && now < startMs) timing = `Opens in ${formatRemaining(startMs - now)}`;
    else if (now < endMs) timing = `Closes in ${formatRemaining(endMs - now)}`;
    else timing = 'Declare window closed — the draw runs within 5 minutes.';
  }

  return (
    <div
      role="status"
      className="rounded-2xl border border-kirro/40 bg-kirro/5 p-4 text-sm"
    >
      <p className="font-medium text-foreground">Demo event ready: {demo.name}</p>
      <p className="mt-1 text-muted-foreground">
        Start the call and ask KIRRO for this one — say the name, your group size and the most you
        will pay. It is a fair draw, so the result follows once the window closes.
      </p>
      <p className="mt-2 text-muted-foreground">
        {demo.slots
          .map(slot => `${slot.label} — ${formatPaise(slot.price_per_person_paise)}`)
          .join(' · ')}
      </p>
      {timing ? (
        <p className="mt-2 font-mono text-xs tracking-wide text-muted-foreground uppercase">{timing}</p>
      ) : null}
    </div>
  );
}
