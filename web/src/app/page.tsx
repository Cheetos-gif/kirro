import { isApiError } from '@/api';
import { AllocationFlow } from '@/components/marketing/allocation-flow';
import { AgentStats } from '@/components/marketing/agent-stats';
import { ArchitectureDiagram } from '@/components/marketing/architecture-diagram';
import { DrawVisualizer } from '@/components/marketing/draw-visualizer';
import { EvidenceGrid } from '@/components/marketing/evidence-grid';
import { InventoryList } from '@/components/marketing/inventory-list';
import { MechanismTimeline } from '@/components/marketing/mechanism-timeline';
import { SectionLabel } from '@/components/marketing/section-label';
import { QuickDemoButton } from '@/components/quick-demo-button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AGENTICORG_URL } from '@/constants';
import { currentViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import type { AgentStat, KirroEvent, Organiser, ReleaseDetail } from '@/lib/kirro/schemas';

/**
 * The organiser the seeded catalogue fixture belongs to (`mock_server/state.py` `_seed_domain`).
 * Anything else was created through the portal — either by a real organiser or by the homepage's
 * demo button — and is shown after the curated listings.
 */
const SEED_ORGANISER_ID = 'org_seed';

export default async function HomePage() {
  const viewer = await currentViewer();

  // Mirrored agent stats (ADR-020). Deliberately tolerant: these are a stat strip, and a sync that
  // has never run (or a mock without the route) must not blank the whole homepage.
  let agentStats: AgentStat[] = [];
  try {
    agentStats = await api.getAgentStats();
  } catch {
    agentStats = [];
  }

  let releases: Array<{
    detail: ReleaseDetail;
    event: KirroEvent;
    organiser: Organiser | undefined;
  }>;

  try {
    const [events, organisers, summaries] = await Promise.all([
      api.listEvents({ status: 'published' }),
      api.listOrganisers(),
      api.listReleases(),
    ]);
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
    // Curated catalogue listings lead, organiser-created releases follow. The homepage's demo button
    // seeds a fresh event on every click, so without this the strip would fill up with demo events
    // and push the actual venue catalogue off the end of the visible three.
    releases.sort((a, b) => {
      const aSeed = a.event.organiser_id === SEED_ORGANISER_ID ? 0 : 1;
      const bSeed = b.event.organiser_id === SEED_ORGANISER_ID ? 0 : 1;
      return aSeed - bSeed || a.detail.opens_at.localeCompare(b.detail.opens_at);
    });
  } catch (error) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-16">
        <Alert variant="destructive">
          <AlertTitle>Cannot reach the booking service</AlertTitle>
          <AlertDescription>
            {isApiError(error) ? error.message : 'Something went wrong.'}
            {process.env.NODE_ENV === 'development' ? (
              <>
                {' '}
                Run <code>bash scripts/dev.sh</code> from the repo root, or point{' '}
                <code>MOCK_API_URL</code> at a running server.
              </>
            ) : null}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6">
      {/* Hero: copy on the left, the mechanism on the right. Asymmetric on purpose. */}
      <section className="grid grid-cols-1 gap-10 py-16 sm:py-24 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-7">
          <h1 className="font-heading text-4xl leading-[1.08] font-medium tracking-tight text-foreground sm:text-5xl">
            Booking scarce slots shouldn&apos;t reward whoever clicks fastest.
          </h1>
          <p className="mt-5 max-w-md text-base text-muted-foreground">
            Tell KIRRO the slot you want, your group size, and the most you&apos;ll pay. If it&apos;s
            free, it&apos;s yours. If other people want it too, everyone gets an equal, fair shot
            &mdash; not just whoever showed up first.
          </p>
          {viewer?.role === 'organiser' || viewer?.role === 'admin' ? (
            <div className="mt-6">
              <QuickDemoButton />
            </div>
          ) : null}
        </div>
        <div className="flex items-center lg:col-span-5">
          <AllocationFlow />
        </div>
      </section>

      {/* The draw: the one genuinely interesting mechanism, given the most visual weight. */}
      <section className="border-t border-border py-14">
        <SectionLabel>The draw</SectionLabel>
        <h2 className="mt-2 font-heading text-2xl font-medium tracking-tight text-foreground">
          When a slot fills up, everyone gets a fair shot
        </h2>
        <div className="mt-8">
          <DrawVisualizer />
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-border py-14">
        <h2 className="font-heading text-2xl font-medium tracking-tight text-foreground">
          How it works
        </h2>
        <div className="mt-8">
          <MechanismTimeline />
        </div>
      </section>

      {/* Inventory */}
      <section className="border-t border-border py-14">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-heading text-2xl font-medium tracking-tight text-foreground">
            What&apos;s on sale
          </h2>
          <p className="text-sm text-muted-foreground">Organisers pick a draw or first come, first served.</p>
        </div>
        <div className="mt-6">
          <InventoryList releases={releases} />
        </div>
      </section>

      {/* Architecture */}
      <section className="border-t border-border py-14">
        <p className="text-sm text-muted-foreground">How your request actually gets booked</p>
        <h2 className="mt-2 font-heading text-2xl font-medium tracking-tight text-foreground">
          A real agent handles it, not a form
        </h2>
        <p className="mt-3 max-w-xl text-sm text-muted-foreground">
          This site is one way to declare interest. KIRRO also runs as an agent on Pine
          Labs&apos; AgenticOrg platform &mdash; it does the same declare, draw, and book
          sequence over WhatsApp or chat.
        </p>
        <div className="mt-8">
          <ArchitectureDiagram />
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-6 w-fit"
          render={<a href={AGENTICORG_URL} target="_blank" rel="noreferrer" />}
          nativeButton={false}
        >
          Open KIRRO on AgenticOrg
        </Button>
      </section>

      {/* Evidence */}
      <section className="border-t border-border pt-14 pb-16">
        <h2 className="font-heading text-2xl font-medium tracking-tight text-foreground">
          What&apos;s real
        </h2>
        {agentStats.length ? (
          <div className="mt-6">
            <AgentStats agents={agentStats} />
          </div>
        ) : null}
        <div className="mt-6">
          <EvidenceGrid />
        </div>
      </section>
    </main>
  );
}
