import { env } from '@/env';
import { requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import type { Slot } from '@/lib/kirro/schemas';

import { TalkClient } from './talk-client';

export const metadata = { title: 'Talk to KIRRO' };

/**
 * The conversational channel: a LiveKit room with the agent worker on the other side, Gnani doing
 * the speech on both ends (ADR-017). Signed in like the rest of the portal — it drives a real agent
 * under a real account.
 *
 * The published events are fetched here, server-side, so the client can point at whichever ones the
 * caller names during the call; `web/src/lib/kirro/api.ts` is server-only by design.
 *
 * `?demo=<event_id>` is set by the homepage's "Organise a demo event" button: it names the freshly
 * seeded event and, when its declare window is still about to open, shows the countdown so the caller
 * knows when to start talking (#32).
 */
export default async function TalkPage({
  searchParams,
}: {
  searchParams: Promise<{ demo?: string }>;
}) {
  await requireViewer();
  const events = await api.listEvents({ status: 'published' });
  const { demo } = await searchParams;

  let demoPrompt: { name: string; opensAt: string; startsAt: string | null; slots: Slot[] } | null =
    null;
  const demoEvent = demo ? events.find(event => event.event_id === demo) : undefined;
  if (demoEvent) {
    const summaries = await api.listReleases({ event_id: demoEvent.event_id });
    // A demo event has exactly one release; take the earliest by window close if that ever changes.
    const [first] = summaries.sort((a, b) => a.opens_at.localeCompare(b.opens_at));
    if (first) {
      const release = await api.getRelease(first.release_id);
      demoPrompt = {
        name: demoEvent.name,
        opensAt: release.opens_at,
        startsAt: release.declare_window_starts_at ?? null,
        slots: release.slots,
      };
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-10">
      <header className="mb-8">
        <h1 className="font-heading text-2xl font-medium tracking-tight">Talk to KIRRO</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The same agent that runs on AgenticOrg, reached by voice instead of by form. Tell it the
          event, the date, your group size and your price ceiling; a fair draw decides the rest.
        </p>
      </header>
      <TalkClient serverUrl={env.LIVEKIT_URL} events={events} demo={demoPrompt} />
    </main>
  );
}
