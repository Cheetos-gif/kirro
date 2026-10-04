import { formatDateTime } from '@/lib/kirro/format';
import type { AgentStat } from '@/lib/kirro/schemas';

/** "80.4%" from 0.804, or an em dash when the field is absent — never a fabricated 0%. */
function percent(value: number | undefined): string {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—';
}

function syncedLabel(iso: string | undefined): string | null {
  if (!iso) return null;
  try {
    return `Last synced ${formatDateTime(iso)}`;
  } catch {
    return null; // an unparseable timestamp must not take the page down
  }
}

/**
 * What the agents have actually scored on AgenticOrg, mirrored into the mock by the stats-sync
 * CronJob (ADR-020). Renders nothing at all before the first sync rather than an empty frame or a
 * zero — "no number yet" and "zero" are different claims and only one of them is true here.
 */
export function AgentStats({ agents }: { agents: AgentStat[] }) {
  if (agents.length === 0) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {agents.map(agent => (
        <div key={agent.agent_id} className="rounded-2xl border border-border p-4">
          <div className="flex items-baseline justify-between gap-3">
            <p className="font-heading text-sm font-medium text-foreground">
              {agent.name ?? agent.agent_id}
            </p>
            {agent.status ? (
              <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
                {agent.status}
              </span>
            ) : null}
          </div>
          <p className="mt-2 font-heading text-2xl font-medium text-foreground">
            {percent(agent.accuracy ?? agent.shadow_accuracy_current)}
            <span className="ml-2 font-sans text-sm font-normal text-muted-foreground">
              accuracy
              {typeof agent.shadow_sample_count === 'number'
                ? ` over ${agent.shadow_sample_count} scored turns`
                : ''}
            </span>
          </p>
          {syncedLabel(agent.synced_at) ? (
            <p className="mt-2 text-xs text-muted-foreground">{syncedLabel(agent.synced_at)}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
