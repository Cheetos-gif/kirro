# Kirro Window Allocation — AgenticOrg Workflow spec

The second of two platform objects (ADR-011 §4). Non-conversational: triggered once per release at its `opens_at`
time, runs the fair draw, captures winners, releases losers, and notifies everyone. Owns the parts of the brief's
17-item list that Kirro Declare does not (ADR-011 §4 table, items 9–13, 15 post-pool, 16).

Built via `client.workflows.generate(...)` / `client.workflows.create(...)` (confirmed to exist in the AgenticOrg
SDK — ADR-010) or the `Workflows` dashboard page. Exact Workflow-builder UI (steps, branching, connector-call
syntax) was not inspected live — this spec describes the required steps and contracts; translate into whatever the
Workflow builder's actual primitives are during implementation (ADR-011 §8 step 1).

## 1. Trigger

Scheduled via the native **Agent Scheduler** connector's `schedule_agent_task` (confirmed in the connector catalog,
ADR-010/011). Kirro Declare calls `schedule_agent_task` once it has a release's `opens_at` from `get_release`,
targeting this Workflow with `{release_id}` as the payload. If multiple users declare interest in the same release,
multiple schedule calls will target the same `(workflow, release_id)` — the trigger must be idempotent per
`release_id` (run the draw once, not once per scheduling call). **Unverified**: whether `schedule_agent_task`
de-duplicates by payload or whether the Workflow itself must check "have I already run for this release_id" before
proceeding — verify live; if not de-duplicated, the Workflow's first step must check a `release_already_drawn`
flag (can live on the venue-inventory mock, since it already tracks per-release state).

## 2. Steps

1. **Fetch the pool.** `venue_inventory.list_pool_entries {release_id}` (new op, same mock as
   `declare_interest` — ADR-011 §2). Returns every pending bid: `{declaration_id, user_contact,
acceptable_slot_ids_or_constraints, group_size, min_group_size, max_price_paise, mandate_id}`.
   - Empty pool: nothing to do, end the Workflow.
2. **Fetch the release.** `venue_inventory.get_release {release_id}` for current slots/capacity/`opens_at`.
3. **Run the draw.** `allocator.draw {release_id, window_open_iso: opens_at, slots, bids: <pool, mapped to the
allocator's Bid shape>}` (the budgeted DIFD mock, ADR-011 §2). Returns one `AllocationResult` per bid:
   `{declaration_id, slot_id|null, group_size_allocated, status: ALLOCATED|WAITLISTED|UNALLOCATED, reason}`.
4. **For each ALLOCATED result** (winner):
   a. `venue_inventory.create_hold {release_id, declaration_id, slot_id, quantity: group_size_allocated, ttl_s}`.
   Failure (4xx, slot taken between draw and hold): fall back to the next acceptable slot per the bid's
   preference order if capacity allows, same rule as the existing Python oracle (`agent/core.py` ALLOCATED→
   ALLOCATING→ALLOCATED retry, ADR-011 §3). Exhausted candidates → treat as WAITLISTED (step 5).
   b. `venue_inventory.get_hold {hold_id}` — confirm `status == "active"` before charging.
   c. Compute `charge = group_size_allocated * hold.price_per_unit_paise`; refuse to proceed if
   `charge > group_size * max_price_paise` or `charge > mandate amount` (the same `charge_within_limits` rule
   as the oracle, `agent/policies/money.py`) — this is a hard invariant the Workflow must check itself, not
   delegate to the mock.
   d. `pine_labs_mandate.execute {authorizationId: mandate_id, amount: {value: charge}}`.
   - Failure (declined, HTTP < 500): release the hold (`venue_inventory.release_hold`), release the mandate
     (`pine_labs_mandate.release`), notify as a loss with reason "payment declined" (step 6).
   - Success: continue.
     e. `venue_inventory.confirm_booking {hold_id, payment_id, declaration_id, amount_paise: charge}`.
   - Not confirmed: `pine_labs_mandate.refund` (if the mock exposes it) or at minimum log the inconsistency;
     notify the user their charge could not be confirmed as a booking (never claim success).
   - Confirmed: `pine_labs_mandate.release` for any unused residual mandate amount
     (`group_size * max_price_paise - charge`), notify as a win with the booking reference (step 6).
5. **For each WAITLISTED or UNALLOCATED result** (loser): `pine_labs_mandate.release {authorizationId: mandate_id}`
   to release their full reserved amount immediately — "losing claims aren't released quickly" is an explicit
   brief failure mode; release must happen in the same Workflow run, not deferred. Notify (step 6).
6. **Notify every bid's `user_contact`** via `whatsapp.send_text_message` (native, `whatsapp_kirro`) with the
   outcome: win (event, date, time, slot, amount charged, booking reference) or loss (plain statement, mandate
   released, invite to redeclare for a future window — item 14 of the brief's list, handled by pointing back at
   Kirro Declare).
7. **Mark the release as drawn** (the de-duplication flag from §1) so a second scheduling trigger for the same
   `release_id` is a no-op.

## 3. Idempotency

- The draw itself only runs once per `release_id` (§1/§7).
- Every mandate/hold/booking call reuses the same idempotency-key discipline as the oracle
  (`agent/state/store.py`: `sha256(declaration_id|stage|scope)`) — if the Workflow re-runs a step after a partial
  failure, it must not double-charge or double-hold. This needs an idempotency key field on each of the 3 budgeted
  mock endpoints' write operations, generated the same way.
- If the Workflow itself crashes/restarts mid-run (brief's "agent restart/resume" test case), re-entry must be safe
  per-bid: check whether a winner already has a `hold_id`/`payment_id`/`booking_ref` before repeating a step.

## 4. Failure handling this Workflow owns

| Situation                                                     | Rule                                                                                                                                                                                                                   |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hold fails after a winning draw result                        | Try the bid's next acceptable slot if capacity allows; exhausted → waitlist outcome, release mandate                                                                                                                   |
| Capture fails after a winning hold                            | Release the hold and the mandate; notify as a loss with reason "payment declined", never leave the hold open                                                                                                           |
| Booking-confirm fails after a successful capture              | Attempt a refund; notify the user their charge could not be confirmed as a booking either way — never claim success                                                                                                    |
| Mandate stuck at `create_mandate`-only state (never advanced) | Not reachable from this Workflow — that would mean Kirro Declare created a mandate but never pooled it; see `agent-spec.md` §7 gap note                                                                                |
| Group cannot be fully seated                                  | DIFD already returns a partial `group_size_allocated` within the bid's declared minimum (ADR-002); Workflow charges and books the partial amount, notification states the partial count explicitly                     |
| Two simultaneous winning bids racing the same slot            | Not possible inside one Workflow run (draw assigns capacity once, sequentially, per bid — `allocator/engine.py`); only a concern if two Workflow runs for the same `release_id` overlap, which §1/§7's de-dup prevents |
