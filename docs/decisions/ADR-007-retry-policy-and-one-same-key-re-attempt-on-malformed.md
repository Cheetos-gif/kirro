# ADR-007: Retry policy and one same-key re-attempt on malformed

Status: accepted (2026-10-01)

## Context
Plan: retry timeouts and 5xx once; never 4xx or malformed. But a malformed response to a create-hold call may hide a
processed request, and E09 requires 'malformed then delayed success accepted'.

## Decision
Connector layer retries only timeout and 5xx (same idempotency key). The engine adds exactly one same-key re-attempt for
create_hold, execute_charge and confirm_booking after a malformed response, safe because the upstream is idempotent by
key. Never for 4xx. After that: FAILED with unwinding, or 'could not confirm' wording for payments.

## Consequences
No double holds or double charges (verified in E09 and tests); relies on upstream honouring Idempotency-Key, which must be
verified for real Pine Labs (UNKNOWN today; `capture` accepts an idempotencyKey in the SDK).
