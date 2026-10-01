import type { Metadata } from 'next';
import Link from 'next/link';

import { auth, signOut } from '@/auth';
import { BackendError } from '@/components/backend-error';
import { StateBadge } from '@/components/state-badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { listDeclarations, listEvalRuns } from '@/lib/kirro';
import type { DeclarationSummary, EvalRunSummary } from '@/lib/kirro';

import { EvalRunsTable } from './eval-runs';

export const metadata: Metadata = {
  title: 'Dashboard — KIRRO',
};

export default async function DashboardPage() {
  const session = await auth();
  let data: [DeclarationSummary[], EvalRunSummary[]];
  try {
    data = await Promise.all([listDeclarations(), listEvalRuns()]);
  } catch (error) {
    return <BackendError error={error} context="dashboard data" />;
  }
  const [declarations, evalRuns] = data;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-6 py-16">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">{session?.user?.email}</p>
        </div>
        <form
          action={async () => {
            'use server';
            await signOut();
          }}
        >
          <Button type="submit" variant="outline" size="sm">
            Sign out
          </Button>
        </form>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Declarations</h2>
        {declarations.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing yet — declarations made via /declare will show up here.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Declaration</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Booking ref</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {declarations.map(d => (
                <TableRow key={d.declaration_id}>
                  <TableCell>
                    <Link
                      href={`/dashboard/${d.declaration_id}`}
                      className="text-primary hover:underline"
                    >
                      {d.declaration_id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StateBadge state={d.state} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{d.booking_ref ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Eval runs</h2>
        {evalRuns.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None yet — run{' '}
            <code className="rounded bg-muted px-1 py-0.5">scripts/run_eval.sh all</code>.
          </p>
        ) : (
          <EvalRunsTable runs={evalRuns} />
        )}
      </section>
    </main>
  );
}
