const STEPS = [
  {
    n: '01',
    title: 'Declare',
    body: 'Slots you\u2019d take, group size, price ceiling.',
  },
  {
    n: '02',
    title: 'Reserve',
    body: 'Money held, not a card charge, until the draw is settled.',
  },
  {
    n: '03',
    title: 'Draw',
    body: 'We pick fairly once the window closes.',
  },
  {
    n: '04',
    title: 'Settle',
    body: 'Winners are charged; losers are released.',
  },
] as const;

/**
 * The four-step declare/reserve/draw/settle sequence: a numbered line connecting each step on
 * desktop, divided rows on mobile. This is a genuine ordered sequence, which is why it carries
 * numbered markers.
 */
export function MechanismTimeline() {
  return (
    <div className="flex flex-col divide-y divide-border sm:grid sm:grid-cols-4 sm:gap-6 sm:divide-y-0">
      {STEPS.map((step, index) => (
        <div key={step.n} className="flex flex-col gap-3 py-5 first:pt-0 last:pb-0 sm:py-0">
          <div className="flex items-center">
            <span
              className={`hidden h-px flex-1 bg-border sm:block ${index === 0 ? 'sm:invisible' : ''}`}
              aria-hidden
            />
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border text-[11px] text-muted-foreground">
              {step.n}
            </span>
            <span
              className={`hidden h-px flex-1 bg-border sm:block ${index === STEPS.length - 1 ? 'sm:invisible' : ''}`}
              aria-hidden
            />
          </div>
          <div className="flex flex-col gap-1">
            <p className="font-heading text-base font-medium text-foreground">{step.title}</p>
            <p className="text-sm text-muted-foreground">{step.body}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
