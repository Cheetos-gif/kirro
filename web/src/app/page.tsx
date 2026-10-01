import Image from 'next/image';
import Link from 'next/link';

import { Button } from '@/components/ui/button';

const STEPS = [
  ['Declare', 'State what you want, a price ceiling, before the window opens.'],
  ['Verify', 'Code parses it. Ambiguous ranges get asked again, never guessed.'],
  ['Authorise', 'A capped mandate blocks the money — it is not charged yet.'],
  ['Wait', 'No polling, no refreshing. Arrival time inside the window does not matter.'],
  ['Allocate', 'A deterministic, seeded fair draw assigns slots when the window opens.'],
  [
    'Confirm',
    'Charge and confirm only after both inventory and payment succeed — or release, honestly.',
  ],
] as const;

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-16 px-6 py-24">
      <div className="flex flex-col gap-5">
        <Image src="/kirro.png" alt="" width={56} height={56} className="rounded-xl" priority />
        <h1 className="text-4xl font-semibold tracking-tight">KIRRO</h1>
        <p className="max-w-2xl text-lg leading-8 text-muted-foreground">
          A declared-interest booking agent for scarce inventory — courts, seats, tickets. Speed
          buys nothing by design: you declare before the window opens, a seeded fair draw allocates
          when it does, and money moves only against a confirmed result.
        </p>
        <div className="flex gap-3">
          <Button render={<Link href="/declare" />}>Declare now</Button>
          <Button variant="outline" render={<Link href="/dashboard" />}>
            Dashboard
          </Button>
        </div>
      </div>

      <ol className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STEPS.map(([title, body], i) => (
          <li key={title} className="flex flex-col gap-1.5 rounded-xl border border-border p-5">
            <span className="text-xs font-medium text-muted-foreground">
              {String(i + 1).padStart(2, '0')}
            </span>
            <h2 className="text-base font-semibold">{title}</h2>
            <p className="text-sm leading-6 text-muted-foreground">{body}</p>
          </li>
        ))}
      </ol>

      <p className="text-sm leading-6 text-muted-foreground">
        Built for The Ken&apos;s Case-Build Competition 2026, Round 3 — &ldquo;Getting the
        slot&rdquo;. Never invents a booking reference, a hold id or a payment id: every identifier
        comes from a real connector result, logged and auditable.
      </p>
    </main>
  );
}
