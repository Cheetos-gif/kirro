# AgenticOrg platform bugs — confirmed, not fixable from a `developer`-role account

Two reproducible bugs on `agenticorg.hackathon.pinelabs.com` itself, not in this repo's code. Full evidence trail is
in `platform-map.md`; this file is the short, stable index — what's broken, what was tried, what's needed to fix it.
Also tracked in [issue #10](https://github.com/Cheetos-gif/kirro/issues/10).

## Bug 1 — tool-call arguments arrive corrupted or null, intermittently, per tool

**Symptom.** `create_mandate`'s arguments always arrive intact at the connector. Every other tool's arguments
(`release_id`, `bids`, `group_size`, `authorization_id`, ...) arrive **null most of the time**, correctly for a
window of roughly 1–30 minutes, then null or otherwise wrong again — same agent, same conversation shape, same
tenant-fixed model (`gpt-5.4`). "Wrong" isn't always null: observed shapes include a date string in an id field, a
free-text description in an id field, and all-null. Timestamped mock-log evidence: `platform-map.md` §11.

**Repo-side remedies tried and disproved** (none changed the pattern): typed/defaulted parameters → untyped,
camelCase id aliases declared on all 11 id-taking tools, a five-parameter vs. seven-parameter tool signature,
one-sentence vs. verbose tool descriptions, a brand-new promoted agent, a fresh conversation, tenant tool-catalogue
size, load (fails during idle periods too), schema-change timing.

**What's needed.** A platform engineering answer: why does one tool's arguments survive the same request pipeline
end-to-end while a structurally identical tool's do not? Is there a per-tool or per-connector rate limit, cache, or
argument-serialization path that treats `create_mandate` differently? Nothing further is testable from this account.

**Blocks.** L09, L14 (before its lucky window), L15, L16 (before their lucky window) — now passing, see
`docs/testing.md` — plus any future eval run has to work around the same intermittent window.

## Bug 2 — the "Kirro Window Allocation" Workflow executes zero steps on every run

**Symptom.** The Workflow is defined correctly (7 steps, `kirro_allocator` agent type, `trigger_type: schedule`,
cron `5 6 * * *`), the trigger fires, but every run produces **no connector request at any step** and **no Audit
Log event at all**. Driving the same agent directly by chat (bypassing the Workflow entirely) executes every tool
correctly, modulo Bug 1. Evidence: `platform-map.md` §12.

**Repo-side remedies tried and disproved**: agent_id vs. agent_type step binding, qualified vs. bare action names,
shadow vs. active agent maturity, a stale connector reference on the bound agent, payload shape, an explicit step
`type` field.

**What's needed.** `GET /api/v1/workflow-runs/{id}` (the run-level step trace) is OAuth-gated — 401 from this
account — so there is no way to see *why* the engine produces zero steps. Needs `agenticorg:admin` access to this
tenant, or a platform engineer with run-trace visibility.

**Blocks.** L17–L22 (every eval that specifically exercises the Workflow, not just a chat-driven agent) and the
daily unattended run this Virtual Employee is meant to perform.

## What was checked before concluding these need admin/platform help

No support, feedback, or contact-platform-admin channel exists anywhere in the `developer`-role UI (checked the
full left nav; nothing under Support/Help routes to a ticket or escalation). The only OAuth-gated endpoints found
(`workflow-runs/{id}`, `connectors/{id}/health` via `POST`, the agent scheduler's native tool) are all genuinely
unreachable, not just unlinked from the UI — confirmed by direct API calls, not just missing buttons.
