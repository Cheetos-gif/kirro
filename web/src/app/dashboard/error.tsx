'use client';

import { Button } from '@/components/ui/button';

// Covers /dashboard and /dashboard/[id]. The read paths in lib/kirro.ts validate every response, so
// a KIRRO Core that is down, unreachable, or returning an unexpected shape lands here with a real
// message instead of rendering a half-populated table.
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-start gap-4 px-6 py-24">
      <h1 className="text-xl font-semibold tracking-tight">Could not load dashboard data</h1>
      <p className="text-sm text-muted-foreground">
        KIRRO Core did not return the expected data. It may be unreachable, restarting, or returning
        a malformed response.
      </p>
      <pre className="w-full overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 text-xs">
        {error.message}
      </pre>
      <Button onClick={reset}>Retry</Button>
    </main>
  );
}
