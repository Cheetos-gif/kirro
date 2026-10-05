/**
 * A quiet orientation line before a diagram — sentence case, not a tracked-out uppercase eyebrow.
 * Used sparingly, only where a reader needs context before the visual that follows it.
 */
export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}
