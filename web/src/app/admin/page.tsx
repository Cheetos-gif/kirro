import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { requireRole } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import { formatPaise } from '@/lib/kirro/format';

import { ApproveOrganiserButton, ResetRunButton, ScenarioForm } from './admin-controls';

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="font-mono text-[11px] tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </p>
      <p className="font-heading text-2xl font-medium text-foreground">{value}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export default async function AdminPage() {
  await requireRole('admin');

  let state;
  let organisers;
  let events;
  try {
    [state, organisers, events] = await Promise.all([
      api.adminState(),
      api.listOrganisers(),
      api.listEvents(),
    ]);
  } catch (error) {
    return (
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-16">
        <Alert variant="destructive">
          <AlertTitle>Cannot reach the booking service</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Something went wrong.'}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const pending = organisers.filter(organiser => organiser.status === 'pending');

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
      <h1 className="font-heading text-2xl font-medium tracking-tight text-foreground">Admin</h1>

      <section className="mt-8 grid grid-cols-2 gap-6 border-t border-border py-6 sm:grid-cols-4">
        <Stat label="Events" value={String(state.events)} hint={`${state.releases} releases`} />
        <Stat
          label="Organisers"
          value={String(state.organisers)}
          hint={`${pending.length} waiting`}
        />
        <Stat
          label="Draw entries"
          value={String(state.declarations)}
          hint={`${state.bookings} bookings`}
        />
        <Stat
          label="Captured (mock)"
          value={formatPaise(state.captured_paise)}
          hint={`${formatPaise(state.refunded_paise)} refunded`}
        />
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Organiser requests</h2>
        <p className="mt-1 text-sm text-muted-foreground">People asking to organise events.</p>
        {pending.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Nothing waiting.</p>
        ) : (
          <Table className="mt-4">
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Requested by</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {pending.map(organiser => (
                <TableRow key={organiser.organiser_id}>
                  <TableCell className="font-medium">{organiser.name}</TableCell>
                  <TableCell>{organiser.contact}</TableCell>
                  <TableCell className="text-muted-foreground">{organiser.requested_by}</TableCell>
                  <TableCell>
                    <ApproveOrganiserButton organiserId={organiser.organiser_id} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">All organisers</h2>
        <Table className="mt-4">
          <TableHeader>
            <TableRow>
              <TableHead>Id</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Requested by</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {organisers.map(organiser => (
              <TableRow key={organiser.organiser_id}>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {organiser.organiser_id}
                </TableCell>
                <TableCell className="font-medium">{organiser.name}</TableCell>
                <TableCell>
                  <Badge variant={organiser.status === 'approved' ? 'secondary' : 'outline'}>
                    {organiser.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {organiser.requested_by ?? 'none'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Events</h2>
        <Table className="mt-4">
          <TableHeader>
            <TableRow>
              <TableHead>Id</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Organiser</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map(event => (
              <TableRow key={event.event_id}>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {event.event_id}
                </TableCell>
                <TableCell className="font-medium">{event.name}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {event.organiser_id}
                </TableCell>
                <TableCell>
                  <Badge variant={event.status === 'published' ? 'secondary' : 'outline'}>
                    {event.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Demo controls</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Make the next call to a target behave badly, so a failure can be shown live. Only affects
          this run.
        </p>
        <div className="mt-4 flex flex-col gap-6">
          <ScenarioForm />
          <ResetRunButton />
        </div>
      </section>
    </main>
  );
}
