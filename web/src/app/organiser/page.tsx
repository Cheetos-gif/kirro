import Link from 'next/link';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import { formatDate } from '@/lib/kirro/format';

import { CreateEventForm, CreateReleaseForm, EventStatusForm } from './organiser-forms';

export default async function OrganiserPage() {
  const viewer = await requireViewer();

  const mine = (await api.listOrganisers()).find(
    organiser =>
      organiser.status === 'approved' &&
      organiser.requested_by?.toLowerCase() === viewer.email.toLowerCase()
  );
  if (!mine) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-16">
        <Alert>
          <AlertTitle>You are not an organiser yet</AlertTitle>
          <AlertDescription className="flex flex-col gap-3">
            <span>Send a request and the team will approve it.</span>
            <Button size="sm" className="w-fit" render={<Link href="/organiser/request" />}>
              Ask to organise
            </Button>
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const events = await api.listEvents({ organiser_id: mine.organiser_id });
  const eventIds = new Set(events.map(event => event.event_id));
  const releases = (await api.listReleases()).filter(release => eventIds.has(release.event_id));
  const withCounts = await Promise.all(
    releases.map(async release => {
      const pool = await api
        .listDeclarations(release.release_id)
        .catch(() => ({ declarations: [] }));
      return { release, declared: pool.declarations.length };
    })
  );

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10">
      <header className="mb-6">
        <h1 className="font-heading text-2xl font-semibold tracking-tight">{mine.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Organiser dashboard, {viewer.email}</p>
      </header>

      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Your events</CardTitle>
            <CardDescription>
              Draft events stay out of the listings until you publish them.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No events yet.</p>
            ) : (
              events.map(event => {
                const eventReleases = withCounts.filter(
                  row => row.release.event_id === event.event_id
                );
                return (
                  <div key={event.event_id} className="flex flex-col gap-2 rounded-2xl border p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="flex items-center gap-2">
                        <span className="font-medium">{event.name}</span>
                        <Badge variant={event.status === 'published' ? 'secondary' : 'outline'}>
                          {event.status}
                        </Badge>
                      </span>
                      <EventStatusForm event={event} />
                    </div>
                    {eventReleases.length === 0 ? (
                      <p className="text-xs text-muted-foreground">No releases yet.</p>
                    ) : (
                      <ul className="flex flex-col gap-1 text-sm">
                        {eventReleases.map(({ release, declared }) => (
                          <li
                            key={release.release_id}
                            className="flex flex-wrap items-center gap-x-3 gap-y-1"
                          >
                            <span className="text-muted-foreground">
                              {formatDate(release.opens_at)}
                            </span>
                            <Badge
                              variant={
                                release.allocation_mode === 'fair_draw' ? 'default' : 'secondary'
                              }
                            >
                              {release.allocation_mode === 'fair_draw' ? 'Draw' : 'Buy now'}
                            </Badge>
                            <span>
                              {release.allocation_mode === 'fair_draw'
                                ? `${declared} in the draw`
                                : 'sells in order of arrival'}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>New event</CardTitle>
          </CardHeader>
          <CardContent>
            <CreateEventForm />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>New release</CardTitle>
            <CardDescription>
              A release belongs to one of your events. A draw release can only be joined by entering
              the draw; a buy-now release sells in order of arrival.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CreateReleaseForm events={events} />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
