import { env } from '@/env';
import { requireViewer } from '@/lib/auth/roles';

import { TalkClient } from './talk-client';

export const metadata = { title: 'Talk to KIRRO' };

/**
 * The conversational channel: a LiveKit room with the agent worker on the other side, Gnani doing
 * the speech on both ends (ADR-017). Signed in like the rest of the portal — it drives a real agent
 * under a real account.
 */
export default async function TalkPage() {
  await requireViewer();

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-10">
      <header className="mb-8">
        <h1 className="font-heading text-2xl font-medium tracking-tight">Talk to KIRRO</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The same agent that runs on AgenticOrg, reached by voice instead of by form. Tell it the
          event, the date, your group size and your price ceiling; a fair draw decides the rest.
        </p>
      </header>
      <TalkClient serverUrl={env.LIVEKIT_URL} />
    </main>
  );
}
