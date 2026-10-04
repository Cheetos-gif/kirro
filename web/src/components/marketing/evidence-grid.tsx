const COLUMNS = [
  {
    label: 'Built',
    items: ['Agent on AgenticOrg', 'Mock venue, payment, and draw services'],
  },
  {
    label: 'Tested',
    items: ['The draw is deterministic and never overbooks a slot', 'Live agent runs, logged with failures found'],
  },
  {
    label: 'Mocked',
    items: ['Inventory, holds, bookings', 'Payment hold and capture'],
  },
] as const;

/**
 * Replaces the old disclaimer card. Same honesty, read as evidence rather than a caveat.
 */
export function EvidenceGrid() {
  return (
    <div className="grid grid-cols-1 gap-6 border-t border-border pt-6 sm:grid-cols-3">
      {COLUMNS.map(column => (
        <div key={column.label}>
          <p className="text-sm text-muted-foreground">{column.label}</p>
          <ul className="mt-2 flex flex-col gap-1">
            {column.items.map(item => (
              <li key={item} className="text-sm text-foreground">
                {item}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
