import Image from 'next/image';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardTitle } from '@/components/ui/card';

const STEPS = [
  ['Declare', 'Say what you want and your max price, before the window opens.'],
  ['Wait', 'We hold your spot. No refreshing, no racing to click first.'],
  ['Allocate', 'A fair random draw runs the moment the window opens.'],
  ['Confirm', "You're only charged if you actually get a slot."],
] as const;

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-16 px-6 py-24">
      <div className="flex flex-col gap-5">
        <Image src="/kirro.png" alt="" width={56} height={56} className="rounded-xl" priority />
        <h1 className="text-4xl font-semibold tracking-tight">KIRRO</h1>
        <p className="max-w-xl text-lg leading-8 text-muted-foreground">
          Book scarce slots — courts, seats, tickets — without racing the clock. Say what you want,
          and we handle the rest.
        </p>
        <div className="flex gap-3">
          <Button render={<Link href="/declare" />}>Declare now</Button>
          <Button variant="outline" render={<Link href="/dashboard" />}>
            Dashboard
          </Button>
        </div>
      </div>

      <ol className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(([title, body], i) => (
          <Card key={title} className="gap-1.5 p-5">
            <span className="text-xs font-medium text-muted-foreground">
              {String(i + 1).padStart(2, '0')}
            </span>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription>{body}</CardDescription>
          </Card>
        ))}
      </ol>

      <p className="text-sm text-muted-foreground">
        Built for The Ken&apos;s Case-Build Competition 2026. Nothing is ever marked booked until
        the venue and payment both confirm it.
      </p>
    </main>
  );
}
