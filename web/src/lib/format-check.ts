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
