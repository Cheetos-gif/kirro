import { isApiError } from '@/api';

// Rendered by a page when a KIRRO Core read fails, instead of letting the error escape to the
// route error boundary: Next.js replaces Server Component error messages with a generic string in
// production, so the boundary shows no cause. Catching here means the real reason is visible where
// it matters. The message is from our own backend (validation / network), not user input.
export function BackendError({ error, context }: { error: unknown; context: string }) {
  const reason = isApiError(error) ? error.message : 'Unexpected error';
  const status = isApiError(error) && error.status ? ` (HTTP ${error.status})` : '';
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-3 px-6 py-24">
      <h1 className="text-xl font-semibold tracking-tight">Could not load {context}</h1>
      <p className="text-sm text-muted-foreground">
        KIRRO Core did not return usable data — it may be down, restarting, or returning a shape
        this page does not expect.
      </p>
      <pre className="w-full overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 text-xs">
        {reason}
        {status}
      </pre>
    </main>
  );
}
