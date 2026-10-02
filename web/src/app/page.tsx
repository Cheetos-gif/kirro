import { isApiError } from '@/api';
import { AllocationFlow } from '@/components/marketing/allocation-flow';
import { ArchitectureDiagram } from '@/components/marketing/architecture-diagram';
import { DrawVisualizer } from '@/components/marketing/draw-visualizer';
import { EvidenceGrid } from '@/components/marketing/evidence-grid';
import { InventoryList } from '@/components/marketing/inventory-list';
import { MechanismTimeline } from '@/components/marketing/mechanism-timeline';
import { SectionLabel } from '@/components/marketing/section-label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AGENTICORG_URL } from '@/constants';
import * as api from '@/lib/kirro/api';
import type { KirroEvent, Organiser, ReleaseDetail } from '@/lib/kirro/schemas';

export default async function HomePage() {
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
          <p className="font-mono text-xs tracking-wide text-muted-foreground">
            declare <span className="text-kirro">&rarr;</span> draw{' '}
            <span className="text-kirro">&rarr;</span> book
          </p>
          <h1 className="mt-4 max-w-xl font-heading text-4xl leading-[1.08] font-medium tracking-tight text-foreground sm:text-5xl">
            Booking scarce slots shouldn&apos;t reward whoever clicks fastest.
          </h1>
          <p className="mt-5 max-w-md text-base text-muted-foreground">
            KIRRO holds your spot, enters a seeded draw when a slot is contested, and books it
            outright when it isn&apos;t. Arrival time decides nothing.
          </p>
        </div>
        <div className="flex items-center lg:col-span-5">
          <AllocationFlow />
        </div>
      </section>

      {/* The draw: the one genuinely interesting mechanism, given the most visual weight. */}
      <section className="border-t border-border py-14">
        <SectionLabel>The draw</SectionLabel>
        <h2 className="mt-2 font-heading text-2xl font-medium tracking-tight text-foreground">
          One seeded draw, run once the window closes
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
        <SectionLabel>How a request reaches the mock services</SectionLabel>
        <h2 className="mt-2 font-heading text-2xl font-medium tracking-tight text-foreground">
          The agent, not the form
        </h2>
        <p className="mt-3 max-w-xl text-sm text-muted-foreground">
          This site is one way to declare interest. KIRRO runs as a Virtual Employee on Pine
          Labs&apos; AgenticOrg platform &mdash; the agent does the same declare, draw, and book
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
        <div className="mt-6">
          <EvidenceGrid />
        </div>
      </section>
    </main>
  );
}
