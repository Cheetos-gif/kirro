import { notFound } from 'next/navigation';

import { SignInButton } from '@/components/auth-buttons';
import { TalkToKirro } from '@/components/talk-to-kirro';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { Viewer } from '@/lib/auth/roles';
import { currentViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import { formatDateTime, formatPaise } from '@/lib/kirro/format';
import type { Slot } from '@/lib/kirro/schemas';

import { BuyForm } from './buy-form';
import { DeclareForm } from './declare-form';

async function ActionPanel({
  releaseId,
  mode,
  slots,
  viewer,
}: {
  releaseId: string;
  mode: 'fair_draw' | 'instant_buy';
  slots: Slot[];
  viewer: Viewer | null;
}) {
  if (!viewer) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sign in to take part</CardTitle>
          <CardDescription>
            {mode === 'fair_draw'
              ? 'We need an account so the draw result reaches you.'
              : 'We need an account so the booking is yours.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SignInButton />
        </CardContent>
      </Card>
    );
  }
  return mode === 'instant_buy' ? (
    <BuyForm releaseId={releaseId} slots={slots} />
  ) : (
    <DeclareForm releaseId={releaseId} slots={slots} />
  );
}

async function loadEvent(id: string) {
  const events = await api.listEvents();
  const event = events.find(candidate => candidate.event_id === id);
  const summaries = event ? await api.listReleases({ event_id: id }) : [];
  const releases = await Promise.all(summaries.map(summary => api.getRelease(summary.release_id)));
  return { event, releases };
}

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const viewer = await currentViewer();

  // notFound() must not run inside this catch: it throws a control-flow signal that a broad catch would eat.
  const loaded = await loadEvent(id).catch((error: unknown) => ({ error }));
  if ('error' in loaded) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-16">
        <Alert variant="destructive">
          <AlertTitle>Cannot reach the booking service</AlertTitle>
          <AlertDescription>
            {loaded.error instanceof Error ? loaded.error.message : 'Something went wrong.'}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const { event, releases } = loaded;
  if (!event) notFound();

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10">
      <header className="mb-6">
        <h1 className="font-heading text-2xl font-semibold tracking-tight">{event.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {event.fulfilment === 'physical' ? 'Posted to you' : 'Digital tickets'}
        </p>
      </header>

      <div className="flex flex-col gap-6">
        {releases.map(release => (
          <Card key={release.release_id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span>{release.release_id}</span>
                <Badge variant={release.allocation_mode === 'fair_draw' ? 'default' : 'secondary'}>
                  {release.allocation_mode === 'fair_draw' ? 'Draw' : 'Buy now'}
                </Badge>
              </CardTitle>
              <CardDescription>Opens {formatDateTime(release.opens_at)}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <ul className="flex flex-col gap-2 text-sm">
                {release.slots.map(slot => (
                  <li
                    key={slot.slot_id}
                    className="flex items-baseline justify-between gap-4 border-b pb-2"
                  >
                    <span>
                      {slot.label}
                      <span className="block text-xs text-muted-foreground">
                        {formatDateTime(slot.starts_at)}
                      </span>
                    </span>
                    <span className="text-right whitespace-nowrap">
                      {formatPaise(slot.price_per_person_paise)}
                      <span className="block text-xs text-muted-foreground">
                        {slot.capacity} left
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
              {release.allocation_mode === 'fair_draw' ? (
                <Alert>
                  <AlertTitle>This one goes to a draw</AlertTitle>
                  <AlertDescription>
                    Add your name and the draw decides who gets the seats. Joining early does not
                    improve your chances.
                  </AlertDescription>
                </Alert>
              ) : null}
              <ActionPanel
                releaseId={release.release_id}
                mode={release.allocation_mode}
                slots={release.slots}
                viewer={viewer}
              />
            </CardContent>
          </Card>
        ))}
        {releases.length === 0 ? (
          <Alert>
            <AlertTitle>Nothing on sale here yet</AlertTitle>
            <AlertDescription>This event has no release open at the moment.</AlertDescription>
          </Alert>
        ) : null}

        <TalkToKirro />
      </div>
    </main>
  );
}
