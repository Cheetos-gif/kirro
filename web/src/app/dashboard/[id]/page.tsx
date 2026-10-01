import type { Metadata } from 'next';
import Link from 'next/link';

import { BackendError } from '@/components/backend-error';
import { StateBadge } from '@/components/state-badge';
import { Card } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { getDecisionLog, getDeclarationFull } from '@/lib/kirro';
import type { DecisionRecord, DeclarationFull } from '@/lib/kirro';

export const metadata: Metadata = {
  title: 'Declaration — KIRRO Dashboard',
};

export default async function DeclarationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let data: [DeclarationFull, DecisionRecord[]];
  try {
    data = await Promise.all([getDeclarationFull(id), getDecisionLog(id)]);
  } catch (error) {
    return <BackendError error={error} context={`declaration ${id}`} />;
  }
  const [declaration, log] = data;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-16">
      <div className="flex flex-col gap-2">
        <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
          ← Dashboard
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{id}</h1>
          <StateBadge state={declaration.state} />
        </div>
      </div>

      <Card className="grid grid-cols-2 gap-x-8 gap-y-3 p-5 text-sm sm:grid-cols-3">
        <Field label="Event" value={declaration.event_name} />
        <Field label="Date" value={declaration.date} />
        <Field label="Group size" value={declaration.group_size} />
        <Field label="Max price (paise)" value={declaration.max_price_paise} />
        <Field label="Mandate" value={declaration.mandate_id} />
        <Field label="Mandate (paise)" value={declaration.mandate_paise} />
        <Field label="Hold" value={declaration.hold_id} />
        <Field label="Payment" value={declaration.payment_id} />
        <Field label="Booking ref" value={declaration.booking_ref} />
        <Field label="Slot" value={declaration.slot_label} />
        <Field label="Terminal reason" value={declaration.terminal_reason} />
      </Card>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Decision log</h2>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Seq</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>By</TableHead>
                <TableHead>Rule</TableHead>
                <TableHead>Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {log.map(r => (
                <TableRow key={r.seq}>
                  <TableCell>{r.seq}</TableCell>
                  <TableCell className="whitespace-nowrap">{r.ts}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    {r.state_before} → {r.state_after}
                  </TableCell>
                  <TableCell className="max-w-48 min-w-48 whitespace-normal">
                    {r.decision}
                  </TableCell>
                  <TableCell>{r.decided_by}</TableCell>
                  <TableCell className="max-w-64 min-w-64 whitespace-normal">{r.rule}</TableCell>
                  <TableCell>{r.result}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-medium">{value ?? '—'}</span>
    </div>
  );
}
