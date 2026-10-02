import Link from 'next/link';

import { formatDate, formatPaise } from '@/lib/kirro/format';
import type { KirroEvent, Organiser, ReleaseDetail } from '@/lib/kirro/schemas';

export function InventoryList({
  releases,
}: {
  releases: Array<{ detail: ReleaseDetail; event: KirroEvent; organiser: Organiser | undefined }>;
}) {
  if (releases.length === 0) {
    return <p className="border-t border-border py-8 text-sm text-muted-foreground">Nothing is on sale right now.</p>;
  }

  return (
    <div className="border-t border-border">
      {releases.map(({ detail, event, organiser }) => {
        const prices = detail.slots.map(slot => slot.price_per_person_paise);
        const seats = detail.slots.reduce((total, slot) => total + slot.capacity, 0);
        const soldOut = seats === 0;
        const isDraw = detail.allocation_mode === 'fair_draw';

        const row = (
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-border py-5">
            <div className="min-w-0">
              <p className="font-heading text-base font-medium text-foreground">{event.name}</p>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {organiser?.name ?? 'Unknown organiser'} &middot; {isDraw ? 'Draw' : 'On sale'}{' '}
                {formatDate(detail.opens_at)} &middot; {detail.slots.length} slot
                {detail.slots.length === 1 ? '' : 's'} &middot; {seats} seat{seats === 1 ? '' : 's'}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {soldOut ? (
                <span className="font-mono text-xs text-muted-foreground">Sold out</span>
              ) : (
                <span className="font-mono text-xs text-foreground">
                  {formatPaise(Math.min(...prices))}/person
                </span>
              )}
              <span
                className={
                  isDraw
                    ? 'font-mono text-xs tracking-wide text-kirro'
                    : 'font-mono text-xs tracking-wide text-muted-foreground'
                }
              >
                {soldOut ? '' : isDraw ? 'DRAW \u2192' : 'BUY NOW \u2192'}
              </span>
            </div>
          </div>
        );

        return soldOut ? (
          <div key={detail.release_id} className="opacity-60">
            {row}
          </div>
        ) : (
          <Link
            key={detail.release_id}
            href={`/events/${event.event_id}`}
            className="block transition-colors hover:bg-foreground/[0.03]"
          >
            {row}
          </Link>
        );
      })}
    </div>
  );
}
