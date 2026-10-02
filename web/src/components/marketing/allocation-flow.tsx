const STAGES = [
  { label: 'Declarations', detail: 'Slot, group size, price ceiling' },
  { label: 'Release window', detail: 'Pool stays open, nothing is charged' },
  { label: 'Fair draw', detail: 'Seeded order, arrival time ignored' },
] as const;

/**
 * The hero mechanism diagram: declarations flow into a window, the window closes into a seeded
 * draw, and the draw splits into winners (charged) and losers (released). Pure CSS, no client JS —
 * this renders in the server-rendered hero.
 */
export function AllocationFlow() {
  return (
    <div className="flex flex-col items-start gap-0 font-mono text-xs tracking-tight text-muted-foreground">
      {STAGES.map((stage, index) => (
        <div key={stage.label} className="flex flex-col items-start">
          <div className="flex items-center gap-3">
            <span className="flex size-6 items-center justify-center rounded-full border border-border text-foreground">
              {index + 1}
            </span>
            <div>
              <p className="text-sm font-medium text-foreground">{stage.label}</p>
              <p className="text-xs text-muted-foreground">{stage.detail}</p>
            </div>
          </div>
          <div className="ml-3 h-6 w-px bg-border" aria-hidden />
        </div>
      ))}
      <div className="flex items-center gap-3">
        <span className="flex size-6 items-center justify-center rounded-full border border-kirro text-kirro">
          4
        </span>
        <p className="text-sm font-medium text-foreground">Winners / losers</p>
      </div>
      <div className="mt-3 ml-9 flex gap-6 border-l border-border pl-3">
        <div>
          <p className="text-xs text-kirro">Winners</p>
          <p className="text-xs text-muted-foreground">Charged for what they get</p>
        </div>
        <div>
          <p className="text-xs text-foreground/70">Losers</p>
          <p className="text-xs text-muted-foreground">Reservation released</p>
        </div>
      </div>
    </div>
  );
}
