# AgenticOrg platform bugs — confirmed, not fixable from a `developer`-role account

Three reproducible issues on `agenticorg.hackathon.pinelabs.com` itself, not in this repo's code. Full evidence trail
is in `platform-map.md`; this file is the short, stable index — what's broken, what was tried, what's needed to fix
it. Also tracked in [issue #10](https://github.com/Cheetos-gif/kirro/issues/10).

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

## Bug 3 — no live call channel exists for an agent; the "Voice" feature is unshipped, not access-gated

**Symptom.** The user must be able to call "Kirro Declare" and talk to it (Twilio for the call leg, Gnani/Vachana
for STT/TTS, per `agent-spec.md`). The Agent detail page's own **Voice** tab states: *"Voice is governed at
organisation level. Agent-specific voice assignment, call history, and operational controls will appear here when
the voice use-case builder is available."* No phone number is bound to any agent in this tenant, and there is no
other reachable UI (checked the full `developer`-role nav) or API (every guessed org/voice endpoint returns the
platform's generic unknown-route 401, the same one a deliberately made-up path returns) to configure it. Every live
eval so far (L01-L08, L10, L12-L16) used the text "Chat with Agent" UI, never a real call. Evidence: `platform-map.md`
§"Vachana — re-registered...".

**Separately, even a correctly credentialed non-MCP custom connector cannot pass this platform's own health check.**
Re-registered `mcp_vachana_kirro` with a real, verified-working Gnani API key; `POST /connectors/{id}/health` reports
`{"status": "not_configured", "reason": "No tools discovered for this MCP server"}` regardless — the health checker
always probes for MCP tool discovery, even for a connector registered with the MCP checkbox off. This reconfirms
ADR-011 Risk 2 on a real (not throwaway) connector: a plain-REST custom connector can never show healthy or expose
tools here, whatever its credential.

**Repo-side remedies tried and disproved:** re-registering Vachana with the MCP checkbox on (Vachana's API does not
itself speak MCP, so this just produces 0 tools the same way); looking for an org-settings/voice link anywhere in the
nav (none exists); probing plausible voice API paths directly (all return the same generic 401 as a nonexistent
path, proving it is unbuilt rather than merely unauthorized for this role).

**What's needed.** Either AgenticOrg ships the voice use-case builder referenced in its own UI, or `agenticorg:admin`
confirms there is a reachable configuration path this account cannot see. Building a replacement call-handling
bridge ourselves (receive Twilio's call webhook, call Vachana STT/TTS, drive the agent via its chat API) is new
top-level infrastructure outside this repo's stated scope (`AGENTS.md`) and would need an explicit ADR and
a deliberate scope decision, not a connector fix.

**Blocks.** L11 (the phone-channel eval — there is no live channel to test blocking on), the demo's stated
requirement that a user can call and talk to the agent.

## What was checked before concluding these need admin/platform help

No support, feedback, or contact-platform-admin channel exists anywhere in the `developer`-role UI (checked the
full left nav; nothing under Support/Help routes to a ticket or escalation). The only OAuth-gated endpoints found
(`workflow-runs/{id}`, `connectors/{id}/health` via `POST`, the agent scheduler's native tool) are all genuinely
unreachable, not just unlinked from the UI — confirmed by direct API calls, not just missing buttons.
