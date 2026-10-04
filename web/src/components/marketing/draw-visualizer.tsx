'use client';

import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';

/**
 * Three real outcomes of allocator.engine.allocate, run against the exact bid helper used in
 * tests/test_allocator.py (seed "rel1"/"2026-10-02T06:00:00Z"). Verified by executing the real
 * allocator, not invented: `allocatedIdx` are the declaration indices (0-based, by arrival order)
 * that the engine actually returned ALLOCATED, confirming arrival order has no bearing on the
 * outcome. Case 0 is the worked example in docs/allocation.md.
 */
const CASES = [
  {
    declarations: 6,
    groupSize: 2,
    seatsNote: 'one 4-seat slot',
    allocatedIdx: [1, 5],
    note: 'the most contested kind of release',
  },
  {
    declarations: 8,
    groupSize: 1,
    seatsNote: 'one 3-seat slot',
    allocatedIdx: [1, 2, 3],
    note: 'tighter oversubscription',
  },
  {
    declarations: 10,
    groupSize: 2,
    seatsNote: 'three slots, one priced above every ceiling',
    allocatedIdx: [1, 5, 6, 7],
    note: 'a slot above everyone\u2019s ceiling never fills',
  },
] as const;

const CYCLE_MS = 5200;

export function DrawVisualizer() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const timer = setInterval(() => {
      setIndex(current => (current + 1) % CASES.length);
    }, CYCLE_MS);
    return () => clearInterval(timer);
  }, []);

  const active = CASES[index];
  const chips = Array.from({ length: active.declarations }, (_, i) => ({
    id: i,
    allocated: (active.allocatedIdx as readonly number[]).includes(i),
  }));
  const allocatedCount = active.allocatedIdx.length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <p className="text-[11px] text-muted-foreground">Entries in</p>
          <p className="font-heading text-3xl font-medium text-foreground">
            {active.declarations}
          </p>
          <p className="text-xs text-muted-foreground">
            {active.groupSize} seat{active.groupSize === 1 ? '' : 's'} each, {active.seatsNote}
          </p>
        </div>
        <div className="text-muted-foreground">&rarr;</div>
        <div>
          <p className="text-[11px] text-muted-foreground">How we pick</p>
          <p className="text-sm text-foreground">A fair pick, not a race</p>
          <p className="text-xs text-muted-foreground">Doesn&apos;t matter who asked first</p>
        </div>
        <div className="text-muted-foreground">&rarr;</div>
        <div>
          <p className="text-[11px] text-kirro">Who got a spot</p>
          <p className="font-heading text-3xl font-medium text-foreground">{allocatedCount}</p>
          <p className="text-xs text-muted-foreground">
            {active.declarations - allocatedCount} waitlisted, same order
          </p>
        </div>
      </div>

      <div key={index} className="flex flex-wrap gap-2">
        {chips.map((claim, i) => (
          <div
            key={claim.id}
            className="animate-kirro-rise flex w-11 shrink-0 flex-col items-center gap-1.5 sm:w-12"
            style={{ animationDelay: `${i * 70}ms` }}
          >
            <div
              className={
                claim.allocated
                  ? 'flex h-9 w-full items-center justify-center rounded-sm border border-kirro bg-kirro-dim text-xs font-medium text-kirro sm:h-10 sm:text-sm'
                  : 'flex h-9 w-full items-center justify-center rounded-sm border border-border text-xs text-muted-foreground sm:h-10 sm:text-sm'
              }
            >
              {claim.id + 1}
            </div>
            <span className="text-[9px] text-muted-foreground sm:text-[10px]">
              {claim.allocated ? 'seated' : 'wait'}
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between gap-4">
        <p className="max-w-xl text-xs text-muted-foreground">
          {active.note}. Draw order depends only on the release, the window, and each
          declaration&apos;s recent win count &mdash; never on when you declared.
        </p>
        <div className="flex shrink-0 items-center gap-1.5">
          {CASES.map((c, i) => (
            <Button
              key={c.declarations + c.seatsNote}
              type="button"
              variant="ghost"
              size="icon-xs"
              aria-label={`Show case ${i + 1}`}
              onClick={() => setIndex(i)}
              className={
                i === index
                  ? 'size-1.5 rounded-full border-none bg-kirro p-0'
                  : 'size-1.5 rounded-full border-none bg-border p-0 hover:bg-muted-foreground'
              }
            />
          ))}
        </div>
      </div>
    </div>
  );
}
