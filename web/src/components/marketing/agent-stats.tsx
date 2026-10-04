import CountUp from '@/components/CountUp';
import { formatDateTime } from '@/lib/kirro/format';
import type { AgentStat } from '@/lib/kirro/schemas';

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
      {agents.map(agent => {
        const raw = agent.accuracy ?? agent.shadow_accuracy_current;
        // Rounded before CountUp sees it, so float noise (0.804 x 100 = 80.39999999999999)
        // never shows up as a jittery decimal count.
        const pct = typeof raw === 'number' ? Math.round(raw * 1000) / 10 : null;

        return (
          <div key={agent.agent_id} className="rounded-2xl border border-border p-4">
            <div className="flex items-baseline justify-between gap-3">
              <p className="font-heading text-sm font-medium text-foreground">
                {agent.name ?? agent.agent_id}
              </p>
              {agent.status ? (
                <span className="text-xs text-muted-foreground">{agent.status}</span>
              ) : null}
            </div>
            <p className="mt-2 font-heading text-2xl font-medium text-foreground">
              {pct === null ? (
                '\u2014'
              ) : (
                <>
                  <CountUp to={pct} duration={1} className="tabular-nums" />%
                </>
              )}
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
        );
      })}
    </div>
  );
}
