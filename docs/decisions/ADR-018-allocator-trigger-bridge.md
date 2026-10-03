# ADR-018: a scheduled trigger bridge drives the Allocator agent, in place of the broken native Workflow

Status: accepted (2026-10-03)

## Context

ADR-011 §4 splits KIRRO across two AgenticOrg objects: "Kirro Declare" (conversational) and "Kirro Window
Allocation" (a scheduled Workflow) that reads the declared-interest pool and runs the DIFD draw. The Workflow
is built and its trigger fires, but it executes **zero steps on every run** and writes no Audit Log event at
all — `docs/agenticorg/platform-bugs.md` Bug 2, root-caused and open since 2026-10-02. The one remaining lever,
`GET /api/v1/workflow-runs/{id}`'s run-level step trace, is OAuth-gated and unreachable from a `developer`-role
account. The native **Agent Scheduler** connector (`schedule_agent_task`) that `workflow-spec.md` originally
specified as the trigger is in the connector catalog but not registerable from this account either
(`docs/agenticorg/workflow-spec.md` §1).

Separately, driving the **Allocator agent directly by chat** has been verified working, repeatedly, since
2026-10-02: `docs/testing.md`'s "workflow §2 happy path", L12-L16, and the L15/L16 re-checks all sent one
sentence — *"Run the allocation for release_id \<id>: draw its bids and settle every one."* — to "Kirro
Allocator" over `/api/v1/chat/query`, and the agent correctly called `draw`, `create_hold`, `get_hold`,
`execute`, `release` and `confirm_booking` in order, including the partial-group-fallback and
malformed-retry defects this session's prompt fixes cover. The Allocator's own decision-making was never the
problem; nothing is asking it the question automatically.

Without any trigger, the consequence named in `docs/agenticorg/declare-v6-notes.md` §2 is concrete: "Kirro
Declare v6" tells every successful bidder *"I will message you with the result after the draw"*, and until
something runs the draw, that is false for every bidder, forever.

## Decision

A small, stateless script — `allocator_bridge/` — runs on a Kubernetes CronJob and, once per pass:

1. Lists releases from the mock (`GET /venue/releases`).
1. Keeps the ones whose declare window has closed (`declarations_open: false`), that have not already been
   drawn (`drawn: false` — new field, below), and that have at least one pool entry.
1. For each one, in its own fresh conversation, sends the same verified sentence to "Kirro Allocator"
   (`5591e57a-79f9-4b30-a95e-0b910a467ce3`) over `/api/v1/chat/query`, reusing `voice_bridge.agenticorg.AgentChat`
   — the same login/CSRF/chat-turn client the voice bridge already uses for the Declare agent, since it has no
   voice-specific code in it.

This keeps ADR-011's boundary intact: the script decides **when** to ask, never **what to do**. Every
allocation, capacity check, hold, capture, release and refund decision is still the Allocator agent's own
tool-calling loop against the mock, exactly as already verified by chatting with it directly. It is the same
shape as the voice bridge for the Declare agent (ADR-016/017) — a relay, not a second brain — applied to the
other half of ADR-011 §4's two-object split.

**Idempotency lives in the mock, not the script.** `/allocator/draw`'s handler now sets `drawn: true` on the
release it just drew (`mock_server/app.py`), as a side effect of a real draw happening — not of the trigger
script remembering anything. A release the script has already handed off is simply absent from the next
pass's candidate list; a draw that never actually ran (the handler never executes, e.g. an `upstream_500`
scenario) leaves `drawn` unset, so the next pass retries it. The script itself keeps no checkpoint, no
database, and no PVC — consistent with AGENTS.md's "no new database" rule.

**Why reuse `voice_bridge.agenticorg.AgentChat` rather than writing a second client.** It depends only on
`httpx` and the generic `logging_`/`conversation_log` helpers — nothing LiveKit- or Gnani-specific — so
importing it from `allocator_bridge` adds no new dependency and no duplicated login/CSRF logic. The package
name is a minor accuracy debt (it is no longer only "the voice bridge's own client"); renaming it is left for a
later pass rather than done here, to keep this change to the one thing it is about.

## Consequences

- New top-level package `allocator_bridge/` (config, the candidate/trigger logic, a `python -m` entrypoint) and
  a new `k8s/allocator-cronjob.yaml`, both exceptions to "no new top-level services" granted here, on the same
  basis ADR-016/017 granted one for voice: a trigger for a platform agent that already makes every real
  decision, not a second decision-maker.
- `mock_server/app.py`: `/allocator/draw` sets `drawn: true` on the release it draws; `GET /venue/releases` and
  `GET /venue/releases/{id}` both expose it, additively, alongside `declarations_open`. Documented in
  `docs/connectors.md`; covered by `tests/test_mock_server.py::test_allocator_draw_marks_the_release_drawn`.
- Runs against the same AgenticOrg credentials already in the `kirro-voice` k8s Secret (`AGENTICORG_EMAIL`,
  `AGENTICORG_PASSWORD`) — no new secret.
- Does **not** fix Bug 2 itself. If the platform's native Workflow is ever unblocked (admin access, or a
  platform-side fix), this bridge becomes redundant and should be retired in the same change that cuts over to
  it — it is a stand-in, not a permanent architecture decision.
- Does **not** send the WhatsApp result notification `workflow-spec.md` §4 describes: the Allocator agent is
  not granted `whatsapp_kirro__send_text_message`, and pool entries today carry no `user_contact` (no channel
  collects one yet, voice included). Tracked as open work, not solved by this ADR
  (`docs/agenticorg/declare-v6-notes.md` §2).
- Concurrency: the CronJob's `concurrencyPolicy: Forbid` plus the mock being a single-writer SQLite store
  (ADR-013) means at most one pass runs at a time; two different *releases* in the same pass are independent
  (separate `AgentChat` instances, separate threads).
