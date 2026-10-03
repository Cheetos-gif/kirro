import type { KirroEvent } from './schemas';

/**
 * Which events a piece of spoken text mentions, matched case-insensitively against an event's name
 * and its `aliases`/`generic_aliases` (the fields `mock_server` seeds precisely so free text like
 * "badminton" or "shuttle" resolves to `ev_badminton`).
 *
 * A display heuristic only — it decides what the talk page lists as "mentioned", never anything
 * about a booking. A false positive just shows an extra link; a false negative shows none.
 */
export function matchEventsInText(text: string, events: KirroEvent[]): KirroEvent[] {
  const haystack = text.toLowerCase();
  return events.filter(event =>
    [event.name, ...event.aliases, ...event.generic_aliases].some(needle => {
      const trimmed = needle.trim().toLowerCase();
      // An empty needle would match every string (`''.includes('')`), so it is skipped rather than
      // treated as a match.
      return trimmed !== '' && haystack.includes(trimmed);
    })
  );
}

/**
 * Every event mentioned anywhere in the transcript so far, in the order each was first mentioned.
 * Sticky on purpose: once the caller has named an event, it stays listed for the rest of the call
 * rather than flickering off when the next utterance happens not to repeat it.
 */
export function matchEventsInTranscript(lines: readonly string[], events: KirroEvent[]): KirroEvent[] {
  const seen = new Set<string>();
  const matched: KirroEvent[] = [];
  for (const line of lines) {
    for (const event of matchEventsInText(line, events)) {
      if (!seen.has(event.event_id)) {
        seen.add(event.event_id);
        matched.push(event);
      }
    }
  }
  return matched;
}
