// Non-builtin eval check names are a JSON-encoded assertion object (see evals/harness.py /
// evals/checks.py), e.g. `{"type": "final_state", "equals": "CLOSED"}`. Builtin checks already
// have a plain-English name and are not JSON, so they parse to `null` here.
export function parseCheckName(raw: string): Record<string, unknown> | null {
  const forbidden = raw.startsWith('forbidden: ');
  const body = forbidden ? raw.slice('forbidden: '.length) : raw;
  try {
    const parsed: unknown = JSON.parse(body);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return null;
    return forbidden
      ? { forbidden: true, ...(parsed as Record<string, unknown>) }
      : (parsed as Record<string, unknown>);
  } catch {
    return null;
  }
}

// Check `detail` strings come straight from Python's checks.py (e.g. `str(bad)` for an empty
// list, `f"{...}"` for everything else) — `"[]"` and `"{}"` are real values meaning "nothing
// found", not useful to show next to a passing check.
const EMPTY_DETAILS = new Set(['', '[]', '{}']);
export function isEmptyDetail(detail: string): boolean {
  return EMPTY_DETAILS.has(detail.trim());
}
