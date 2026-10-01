# Demo

## Why this exists

The final recording matters more than polish. This is the intended shape; run ids and timings are filled in after the
first live recording.

## Local rehearsal

Removed with the AgenticOrg migration — see ADR-011. There is no local `scripts/chat.py` rehearsal anymore; KIRRO runs
as an AgenticOrg Virtual Employee and the demo drives it there. Register it with
`docs/agenticorg/setup-runbook.md`, then run the scenario through the platform conversation.

Failure variants are set out of band on the mock server: `POST /__admin/scenario` with, e.g.,
`pinelabs.execute=payment_failure`, `venue.release=no_inventory`, `venue.hold=malformed`.

## Recording plan (TODO: bind to a stored run id)

1. Declaration by voice (Gnani inbound call preferred; outbound needs whitelisted numbers and may be spam-filtered).
1. Read-back and authorisation: mandate equals group x ceiling.
1. Human triggers the window event. Show the allocation seed and order in the log.
1. Hold -> charge -> confirmation with the booking reference.
1. Second take: payment failure -> release, honest message.
1. Delhivery mock only for a physical-pass event (F1 paddock pass).
   The human may simulate external events but must not reason for the agent. Fallback if the call is blocked: continue
   the same AgenticOrg agent over its text channel, reported as a finding.

## Evidence

Removed with the AgenticOrg migration — see ADR-011. Q1.2 reconstruction now needs AgenticOrg's Audit
Log/Observatory (ADR-011 §7.6, open): the platform-hosted agent's decisions live in that audit trail, not in a local
JSONL file.
