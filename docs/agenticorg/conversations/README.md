# Live agent conversation log

Every chat run against a real AgenticOrg agent (`Kirro Declare`, `Kirro Allocator`), from 2026-10-02 onward, gets a
full transcript here — not just the quoted snippet in `docs/testing.md`. `testing.md` stays the verdict log (pass /
fail / evidence / fix); this directory is the raw material behind it, for later review.

## Convention

One file per conversation: `YYYY-MM-DD-HHMMz-<agent>-<case-or-purpose>.md`, UTC timestamp of the first turn,
`<agent>` is `declare` or `allocator`, `<case-or-purpose>` is the eval id (`l09`, `l15`) or a short free label
(`demo-dry-run`, `whatsapp-token-probe`).

Each file:

```markdown
# <case/purpose> — <agent display name> — <UTC timestamp>

Agent id: `<uuid>`. Mock run: `default`. Scenario: `<armed scenario, if any>`.

## Transcript

Full `innerText` of the chat panel, verbatim, captured via the browser tab right after the run.

## Mock log cross-reference

The matching lines from the mock's own `default.jsonl` for this run (target, request, response, status),
so the chat claims can be checked against what the connector actually received and returned.

## Verdict

One line: pass / fail / inconclusive, and why. Cross-reference to the `docs/testing.md` row if one exists.
```

Capture the transcript with `tab.evaluate` reading the dialog's `innerText` right after the run (before the next
message overwrites scroll state) — not reconstructed from memory. If a conversation reused an earlier browser tab
and the panel now only shows the tail, note that explicitly rather than guessing the missing turns.
