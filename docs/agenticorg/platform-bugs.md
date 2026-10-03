# AgenticOrg platform bugs — confirmed, not fixable from a `developer`-role account

Three reproducible issues on `agenticorg.hackathon.pinelabs.com` itself, not in this repo's code. Full evidence trail
is in `platform-map.md`; this file is the short, stable index — what's broken, what was tried, what's needed to fix
it. Bug 1 tracked in [issue #15](https://github.com/Cheetos-gif/kirro/issues/15), Bug 2 in
[issue #16](https://github.com/Cheetos-gif/kirro/issues/16). Bug 3 is resolved (see its entry below).

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

**Blocks.** L17–L22 (every eval that specifically exercises the Workflow, not just a chat-driven agent) directly.
The daily unattended run itself is no longer blocked: `allocator_bridge/` (ADR-018, 2026-10-03) drives "Kirro
Allocator" over its chat API on a k8s CronJob instead of waiting on this Workflow, using the exact chat-driven
path already proven here. This does not fix the Workflow or this bug; it is a stand-in, documented as such in
the ADR, to retire if the Workflow is ever unblocked.

## Bug 3 — no platform-native way to give the agent Gnani-powered voice (resolved)

**Symptom.** The user must be able to talk to "Kirro Declare", with Gnani/Vachana doing STT/TTS. No phone number or
browser-voice deployment is bound to any agent in this tenant; every live eval so far (L01-L08, L10, L12-L16) used
the text "Chat with Agent" UI. A paid phone leg (Twilio) was considered and dropped — it costs money per number and
per call-minute; see `docs/decisions/ADR-016-voice-bridge-for-browser-calls-to-kirro-declare.md`.

**What exists (corrected 2026-10-02; an earlier version of this entry wrongly said the feature was unshipped).**
AgenticOrg has a full voice platform at `/dashboard/voice` (API `/api/v1/voice-platform/*`: profiles, bindings,
deployments, endpoints, release approvals, a browser "studio"). The `/dashboard/voice` page itself returns
*"Your current role can't view /dashboard/voice. REQUIRED ROLE admin"*. From a `developer` session,
`GET /voice-platform/capabilities`, `/profiles` and `/deployments` answer `200`; `/endpoints` and
`/release-approvals` answer `403 Missing scope: agenticorg:admin`; `/integrations` and `/bindings` answer `500`.
`capabilities` reports:

- speech providers `openai`, `gemini` only — **no Gnani/Vachana**;
- channels `browser_webrtc`, `telephony_websocket`, `application_websocket`; telephony adapters
  `generic_json_audio_v1`, `ttbs_smartflo_v1` (no Twilio adapter);
- `developer_browser_testing_available: true`, `release_promotion_required: true`,
  `high_risk_tools_available: false`.

So a developer can probably build and browser-test a voice deployment, though that is untested here. Publishing it
to a phone endpoint needs admin, and the platform's voice runs on OpenAI or Gemini speech, not Gnani. The generic
unknown-route 401 is no evidence that an endpoint is missing: `/api/v1/api-keys` returns that same 401 while
`/api/v1/org/api-keys` returns `403 Missing scope`.

**Separately, a non-MCP custom connector cannot pass this platform's health check.** `mcp_vachana_kirro`,
re-registered with a working Gnani key, reports `{"status": "not_configured", "reason": "No tools discovered for this MCP server"}`. The checker probes for MCP tool discovery even when the MCP checkbox is off (ADR-011 Risk 2).

**Resolution, not platform-dependent: a browser voice channel.** Rather than a phone call, `web/` (the
portal this repo already deploys) gets a "Talk to KIRRO" page that joins a LiveKit room; a self-hosted
`livekit-server` and a `voice_bridge/` agent worker carry the audio, with Gnani's own LiveKit plugin doing
speech-to-text and text-to-speech around the AgenticOrg agent (`docs/decisions/ADR-016-...`,
`docs/decisions/ADR-017-voice-channel-on-livekit.md`). Free — the Gnani key is already live, LiveKit is open
source and self-hosted, no Twilio number, no per-minute telephony or cloud cost — and it needs no
`agenticorg:admin`. Verified end to end on a local room server: a caller's synthesized speech transcribed,
the agent answered, and the reply came back as audio.

**What would still need admin, if the platform-native route is ever preferred instead:** `agenticorg:admin` for
`voice-platform/endpoints` and `/release-approvals`, and accepting OpenAI/Gemini speech instead of Gnani.

**Blocks.** L11 until the bridge is live.

## What was checked before concluding these need admin/platform help

No support, feedback, or contact-platform-admin channel exists anywhere in the `developer`-role UI (checked the
full left nav; nothing under Support/Help routes to a ticket or escalation). The only OAuth-gated endpoints found
(`workflow-runs/{id}`, `connectors/{id}/health` via `POST`, the agent scheduler's native tool) are all genuinely
unreachable, not just unlinked from the UI — confirmed by direct API calls, not just missing buttons.
