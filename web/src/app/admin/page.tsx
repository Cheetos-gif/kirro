import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-xl">{value}</CardTitle>
      </CardHeader>
      {hint ? (
        <CardContent className="pt-0 text-xs text-muted-foreground">{hint}</CardContent>
      ) : null}
    </Card>
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
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-16">
        <Alert variant="destructive">
          <AlertTitle>Could not load admin data</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Mock server unreachable.'}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const pending = organisers.filter(organiser => organiser.status === 'pending');

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
      <h1 className="mb-6 font-heading text-2xl font-semibold tracking-tight">Admin</h1>

      <section className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Events" value={String(state.events)} hint={`${state.releases} releases`} />
        <Stat
          label="Organisers"
          value={String(state.organisers)}
          hint={`${pending.length} pending`}
        />
        <Stat
          label="Declarations"
          value={String(state.declarations)}
          hint={`${state.bookings} bookings`}
        />
        <Stat
          label="Captured"
          value={formatPaise(state.captured_paise)}
          hint={`${formatPaise(state.refunded_paise)} refunded`}
        />
      </section>

      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Pending organiser approvals</CardTitle>
            <CardDescription>Self-serve requests waiting on an admin.</CardDescription>
          </CardHeader>
          <CardContent>
            {pending.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing pending.</p>
            ) : (
              <Table>
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
                      <TableCell className="text-muted-foreground">
                        {organiser.requested_by}
                      </TableCell>
                      <TableCell>
                        <ApproveOrganiserButton organiserId={organiser.organiser_id} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>All organisers</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
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
                    <TableCell className="text-muted-foreground">
                      {organiser.organiser_id}
                    </TableCell>
                    <TableCell className="font-medium">{organiser.name}</TableCell>
                    <TableCell>
                      <Badge variant={organiser.status === 'approved' ? 'secondary' : 'outline'}>
                        {organiser.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {organiser.requested_by ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Events</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
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
                    <TableCell className="text-muted-foreground">{event.event_id}</TableCell>
                    <TableCell className="font-medium">{event.name}</TableCell>
                    <TableCell className="text-muted-foreground">{event.organiser_id}</TableCell>
                    <TableCell>
                      <Badge variant={event.status === 'published' ? 'secondary' : 'outline'}>
                        {event.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Scenario controls</CardTitle>
            <CardDescription>
              Arm a mock failure for the live demo. Harness-only; requests still carry only normal
              payloads.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <ScenarioForm />
            <ResetRunButton />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
