const NODES = [
  { label: 'You', detail: 'WhatsApp or chat' },
  { label: 'KIRRO', detail: 'Declares, reads back, confirms' },
  { label: 'AgenticOrg', detail: "Pine Labs\u2019 agent platform" },
] as const;

const CONNECTORS = [
  { name: 'Venue inventory', does: 'Catalogue, holds, bookings' },
  { name: 'The draw', does: 'Runs the seeded, fair draw' },
  { name: 'Pine Labs', does: 'Holds, charges, and releases payment' },
] as const;

/**
 * How a declaration actually reaches the mock services: you talk to the KIRRO agent, the agent
 * runs on AgenticOrg (Pine Labs' platform), and AgenticOrg calls out to the services below. No
 * invented integrations — these three are the same mocks the rest of this site and
 * docs/connectors.md describe.
 */
export function ArchitectureDiagram() {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col sm:flex-row sm:items-stretch">
        {NODES.map((node, index) => (
          <div key={node.label} className="flex flex-col sm:flex-1 sm:flex-row sm:items-stretch">
            {index > 0 ? (
              <div className="flex h-6 items-center justify-center text-muted-foreground sm:h-auto sm:w-8">
                <span className="sm:hidden">&darr;</span>
                <span className="hidden sm:inline">&rarr;</span>
              </div>
            ) : null}
            <div className="flex flex-1 flex-col gap-0.5 border border-border px-4 py-3.5">
              <p className="font-heading text-sm font-medium text-foreground">{node.label}</p>
              <p className="text-xs text-muted-foreground">{node.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 py-1 pl-1 text-xs text-muted-foreground">
        <span>&darr;</span>
        <span>which in turn relies on</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {CONNECTORS.map(connector => (
          <div key={connector.name} className="flex flex-col gap-0.5 border border-border px-4 py-3">
            <p className="text-xs font-medium text-foreground">{connector.name}</p>
            <p className="text-xs text-muted-foreground">{connector.does}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
