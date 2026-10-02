import Link from 'next/link';

import { isApiError } from '@/api';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import * as api from '@/lib/kirro/api';
import { formatDate, formatPaise } from '@/lib/kirro/format';
import type { KirroEvent, Organiser, ReleaseDetail } from '@/lib/kirro/schemas';

export default async function HomePage() {
  let events: KirroEvent[];
  let organisers: Organiser[];
  let releases: Array<{
    detail: ReleaseDetail;
    event: KirroEvent;
    organiser: Organiser | undefined;
  }>;

  try {
    const [allEvents, allOrganisers, summaries] = await Promise.all([
      api.listEvents({ status: 'published' }),
      api.listOrganisers(),
      api.listReleases(),
    ]);
    events = allEvents;
    organisers = allOrganisers;
    const eventById = new Map(events.map(event => [event.event_id, event]));
    const organiserById = new Map(organisers.map(organiser => [organiser.organiser_id, organiser]));
    const details = await Promise.all(
      summaries
        .filter(summary => eventById.has(summary.event_id))
        .map(async summary => {
          const detail = await api.getRelease(summary.release_id);
          const event = eventById.get(summary.event_id);
          return event ? { detail, event, organiser: organiserById.get(event.organiser_id) } : null;
        })
    );
    releases = details.filter((row): row is NonNullable<typeof row> => row !== null);
  } catch (error) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-16">
        <Alert variant="destructive">
          <AlertTitle>Mock server unreachable</AlertTitle>
          <AlertDescription>
            {isApiError(error) ? error.message : 'Could not load listings.'} Start it with{' '}
            <code>bash scripts/dev.sh</code> or set <code>MOCK_API_URL</code>.
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
      <section className="mb-8">
        <h1 className="font-heading text-2xl font-semibold tracking-tight">Open listings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Scarce inventory books by declared-interest draw; everything else is a plain first-come
          buy. The badge on each listing says which.
        </p>
      </section>

      {releases.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-sm text-muted-foreground">
            No published releases yet. Organisers create them from the organiser dashboard.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {releases.map(({ detail, event, organiser }) => {
            const prices = detail.slots.map(slot => slot.price_per_person_paise);
            const seats = detail.slots.reduce((total, slot) => total + slot.capacity, 0);
            return (
              <Card key={detail.release_id}>
                <CardHeader>
                  <CardTitle>
                    <Link href={`/events/${event.event_id}`} className="hover:underline">
                      {event.name}
                    </Link>
                  </CardTitle>
                  <CardDescription>
                    {organiser?.name ?? 'Unknown organiser'} · {formatDate(detail.opens_at)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={detail.allocation_mode === 'fair_draw' ? 'default' : 'secondary'}
                    >
                      {detail.allocation_mode === 'fair_draw' ? 'Fair draw' : 'Instant buy'}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {detail.slots.length} slot{detail.slots.length === 1 ? '' : 's'} · {seats}{' '}
                      seat
                      {seats === 1 ? '' : 's'}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    From {formatPaise(Math.min(...prices))} per person
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-fit"
                    render={<Link href={`/events/${event.event_id}`} />}
                  >
                    View and book
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </main>
  );
}
