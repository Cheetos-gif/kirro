/**
 * Used sparingly — only where a reader needs orientation before a diagram (not stamped above every
 * section as generic chrome).
 */
export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[11px] tracking-[0.08em] text-muted-foreground uppercase">
      {children}
    </p>
  );
}
