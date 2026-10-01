import type { Metadata } from 'next';
import Link from 'next/link';

import { BackendError } from '@/components/backend-error';
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
      <div className="flex flex-col gap-1">
        <Link href="/dashboard" className="text-sm text-muted-foreground hover:underline">
          ← Dashboard
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">{id}</h1>
        <p className="text-sm text-muted-foreground">
          State: <span className="font-medium text-foreground">{declaration.state}</span>
        </p>
      </div>

      <section className="grid grid-cols-2 gap-x-8 gap-y-2 rounded-xl border border-border p-5 text-sm sm:grid-cols-3">
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
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Decision log</h2>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Seq</th>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">State</th>
                <th className="px-3 py-2 font-medium">Decision</th>
                <th className="px-3 py-2 font-medium">By</th>
                <th className="px-3 py-2 font-medium">Rule</th>
                <th className="px-3 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {log.map(r => (
                <tr key={r.seq} className="border-t border-border align-top">
                  <td className="px-3 py-2">{r.seq}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{r.ts}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.state_before} → {r.state_after}
                  </td>
                  <td className="px-3 py-2">{r.decision}</td>
                  <td className="px-3 py-2">{r.decided_by}</td>
                  <td className="px-3 py-2">{r.rule}</td>
                  <td className="px-3 py-2">{r.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
