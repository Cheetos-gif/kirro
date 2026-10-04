/**
 * A countdown in the shortest form that stays readable at its own scale: `M:SS` under an hour,
 * `H:MM:SS` under a day, `Nd Hh` beyond that.
 *
 * The hour/day branches are not theoretical: a seeded release's declare window is anchored roughly a
 * day ahead (`mock_server/state.py` `_seed_domain`), so a bare `M:SS` formatter renders that as
 * something like `1539:25`.
 */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}:${mm}:${ss}`;
  return `${minutes}:${ss}`;
}
