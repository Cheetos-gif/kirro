import Link from 'next/link';

import { formatDate, formatPaise } from '@/lib/kirro/format';
import type { KirroEvent, Organiser, ReleaseDetail } from '@/lib/kirro/schemas';

type Row = { detail: ReleaseDetail; event: KirroEvent; organiser: Organiser | undefined };

/**
 * The landing page's listing strip. Deliberately short: it shows `limit` releases and, when there
 * are more, one clipped row fading out underneath as a hint that the catalogue continues — the page
 * is a landing page, not an index, and growing it with every demo event seeded would bury the rest.
 *
 * The clipped row is decorative (not a link, `aria-hidden`) rather than a half-clickable target.
 */
export function InventoryList({ releases, limit = 3 }: { releases: Row[]; limit?: number }) {
  if (releases.length === 0) {
    return <p className="border-t border-border py-8 text-sm text-muted-foreground">Nothing is on sale right now.</p>;
  }

  const shown = releases.slice(0, limit);
  const hint = releases.length > limit ? releases[limit] : null;

  function renderRow({ detail, event, organiser }: Row) {
    const prices = detail.slots.map(slot => slot.price_per_person_paise);
    const seats = detail.slots.reduce((total, slot) => total + slot.capacity, 0);
    const soldOut = seats === 0;
    const isDraw = detail.allocation_mode === 'fair_draw';

    return (
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
  }

  return (
    <div className="border-t border-border">
      {shown.map(row =>
        row.detail.slots.reduce((total, slot) => total + slot.capacity, 0) === 0 ? (
          <div key={row.detail.release_id} className="opacity-60">
            {renderRow(row)}
          </div>
        ) : (
          <Link
            key={row.detail.release_id}
            href={`/events/${row.event.event_id}`}
            className="block transition-colors hover:bg-foreground/[0.03]"
          >
            {renderRow(row)}
          </Link>
        )
      )}

      {hint ? (
        <div aria-hidden className="relative max-h-11 overflow-hidden select-none">
          <div className="opacity-60">{renderRow(hint)}</div>
          {/* Fades the clipped row into the page, so it reads as "there is more" rather than a
              half-rendered list. */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent to-background" />
        </div>
      ) : null}
    </div>
  );
}
