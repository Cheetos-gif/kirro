// `open_field_note` from KIRRO Core is the raw parser verdict ("ambiguous" | "invalid" | null),
// not a sentence — AGENTS.md: "field_notes: last parser verdict per field". This turns that plus
// the open field name into something a user filling the web form can act on.
const FIELD_LABELS: Record<string, string> = {
  event: 'what you want to book',
  date: 'the date',
  group_size: 'the group size',
  max_price: 'the max price per person',
  min_group_size: 'the minimum group size',
  time_window: 'the preferred time',
};

export function describeOpenField(field: string, note: string | null): string {
  const label = FIELD_LABELS[field] ?? field;
  if (note === 'ambiguous') return `Give one clear answer for ${label}`;
  if (note === 'invalid') return `Couldn't understand ${label} — try rephrasing`;
  if (note) return `${label}: ${note}`;
  return `Still need ${label}`;
}
