# Demo

## Why this exists

The final recording matters more than polish. This is the intended shape; run ids and timings are filled in after the
first live recording.

## Local rehearsal (works today, offline)

```
uv run python scripts/chat.py
you> Badminton court Saturday 7-9 am, 4 people, max 300 each
you> yes
you> /open          # human simulates the window opening
```

Failure variants: `--scenario pinelabs.execute=payment_failure`, `--scenario venue.release=no_inventory`,
`--scenario venue.hold=malformed`.

## Recording plan (TODO: bind to a stored run id)

1. Declaration by voice (Gnani inbound call preferred; outbound needs whitelisted numbers and may be spam-filtered).
1. Read-back and authorisation: mandate equals group x ceiling.
1. Human triggers the window event. Show the allocation seed and order in the log.
1. Hold -> charge -> confirmation with the booking reference.
1. Second take: payment failure -> release, honest message.
1. Delhivery mock only for a physical-pass event (F1 paddock pass).
   The human may simulate external events but must not reason for the agent. Fallback if the call is blocked: text chat
   runner, reported as a finding.

## Evidence

`scripts/reconstruct.sh evals/runs/<run>/log.jsonl` produces the decision table for Q1.2.
