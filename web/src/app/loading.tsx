/**
 * Root-level loading UI (Next.js App Router convention): shown while a route segment's data is
 * still loading. The header/footer from the root layout stay mounted, so this only needs to fill
 * the `<main>` area — same `max-w-5xl` + `px-6` rhythm every page uses, so nothing jumps when the
 * real content swaps in.
 */
export default function Loading() {
  return (
    <main
      role="status"
      aria-live="polite"
      className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-3 px-6 py-24"
    >
      <span
        aria-hidden
        className="size-8 animate-spin rounded-full border-2 border-border border-t-kirro motion-reduce:animate-none"
      />
      <span className="text-sm text-muted-foreground">Loading…</span>
    </main>
  );
}
