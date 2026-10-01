import type { Metadata } from 'next';

import { DeclareWizard } from './declare-wizard';

export const metadata: Metadata = {
  title: 'Declare — KIRRO',
  description: 'Declare what you want booked, before the window opens.',
};

export default function DeclarePage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center gap-8 px-6 py-16">
      <div className="flex w-full max-w-xl flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Declare</h1>
        <p className="text-sm text-muted-foreground">Tell us what you want in your own words.</p>
      </div>
      <DeclareWizard />
    </main>
  );
}
