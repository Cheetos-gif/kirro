import type { Metadata } from 'next';
import Link from 'next/link';

import { auth, signOut } from '@/auth';
import { Button } from '@/components/ui/button';
import { listDeclarations, listEvalRuns } from '@/lib/kirro';

export const metadata: Metadata = {
  title: 'Dashboard — KIRRO',
};

export default async function DashboardPage() {
  const session = await auth();
  const [declarations, evalRuns] = await Promise.all([listDeclarations(), listEvalRuns()]);

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-10 px-6 py-16">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Signed in as {session?.user?.email}</p>
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
        <h2 className="text-lg font-semibold">Declarations (this process)</h2>
        {declarations.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None yet. State is in memory per process — declarations made via /declare while this
            KIRRO Core instance is running will show up here.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">Declaration</th>
                  <th className="px-4 py-2 font-medium">State</th>
                  <th className="px-4 py-2 font-medium">Booking ref</th>
                </tr>
              </thead>
              <tbody>
                {declarations.map(d => (
                  <tr key={d.declaration_id} className="border-t border-border">
                    <td className="px-4 py-2">
                      <Link
                        href={`/dashboard/${d.declaration_id}`}
                        className="text-primary hover:underline"
                      >
                        {d.declaration_id}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{d.state}</td>
                    <td className="px-4 py-2 text-muted-foreground">{d.booking_ref ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Eval runs</h2>
        {evalRuns.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None recorded yet. Run{' '}
            <code className="rounded bg-muted px-1 py-0.5">scripts/run_eval.sh all</code> on the
            KIRRO Core host to populate this.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {evalRuns.map(r => (
              <li key={r.run_id} className="rounded-lg border border-border p-3 text-sm">
                <span className="font-medium">{r.run_id}</span>{' '}
                <span className="text-muted-foreground">{JSON.stringify(r.verdict)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
