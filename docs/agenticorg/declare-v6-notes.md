# Kirro Declare v6 — known gaps and next improvements

Status as of 2026-10-03: `Kirro Declare v6` (`6596b872-abb5-465a-87d3-fff8de17536d`) is `active` and is the agent the
voice bridge drives (`voice_bridge/config.py` `DEFAULT_AGENT_ID`). Build history, the scoring rule and the L01–L10
results are in `docs/testing.md` ("Kirro Declare v6"); the prompt is `agent-spec.md` §3. This file is the work list,
highest value first. Nothing here is done unless it says so.

How to test any prompt change: edit and re-run on `Kirro Declare v6-dev` (`69766e00-…`, shadow) first, so trial turns
do not land in v6's score; then pause → `PATCH system_prompt_text` → resume v6 (`platform-map.md` §10) and re-run the
affected L-cases in fresh threads, judging by the mock log, never the agent's reply.

## 1. The score can still fall below the floor

The score is the mean of per-turn confidences: 0.85 after any tool attempt in the thread, else 0.60 (reply ≤ 100
chars) or 0.65. v6 sits at 0.808 over only 28 samples, so a handful of tool-less turns pulls it under 0.80 and the
red "Below Floor" badge returns (v4 kept running with it; no other consequence has been observed).

Where tool-less turns still come from:

- **Fixed 2026-10-03: the voice bridge's synthetic "Hi".** Every call used to start with `greet_caller()` sending
  `GREETING_OPENER = "Hi"` through the agent, scoring one tool-less turn per call before the caller ever spoke.
  `greet_caller` now speaks a fixed `GREETING_TEXT` straight through `session.say()` with no AgenticOrg call
  (`voice_bridge/agent.py`); the 60s idle protection is unchanged (`docs/testing.md`, "Superseded 2026-10-03").
- **Fixed 2026-10-03: cumulative transcript re-sends.** On v4, 14 user turns were the previous turn plus more words
  ("solah ek" → "solah ek ek din" → …), each a scored turn and a repeated read-back. `voice_bridge/agenticorg_llm.py`
  `AgenticOrgChat.next_turn_text` now sends only the newest user message, skips an exact repeat, sends only the new
  suffix of a growing one, and logs every skip (`tests/test_voice_bridge.py`). LiveKit does keep one `ChatMessage.id`
  while a late transcript is appended (confirmed by the fix landing cleanly on `latest_user_text`'s existing
  "newest user message" read, not by inspecting LiveKit's own source).
- **Questions before any event is named** (greeting, "what can you do", ambiguous "court"). These are legitimate
  and must stay; they are why chat traffic will hover near, not far above, 0.80.

Do not chase the score with padded replies, gratuitous tool calls or filler conversations (`docs/testing.md` lists
the rejected levers).

## 2. The WhatsApp result notification

- **Wired 2026-10-03 (owner authorized): the draw result now leaves over WhatsApp.** The Meta app's own free test
  number was replaced by a real Business number (`+91 81673 12268`, registered on the Kirro Meta app), its
  permanent access token is in the `whatsapp_kirro` connector, and "Kirro Allocator" is granted
  `whatsapp__send_text_message` with a NOTIFY step in its prompt. A declaration must now carry a `notify_phone`
  (mock-side requirement, portal collects it once in `/settings`, v6 asks for it), so there is always an address to
  notify. Verified live: `whatsapp__send_text_message` delivered a result message to a real handset.
  - **Caveat that shapes the demo:** the WhatsApp Business API only allows a business to send freeform text inside
    a 24-hour window the *user* opens by messaging the business first. WhatsApp-initiated (template) messages need
    an approved template and a payment method, which is out of scope ("no paid plans"). So the demo order is:
    user declares → taps the CTA / messages `+91 81673 12268` once → the Allocator's result lands inside that
    window. v6's closing line now tells the user to send that first message, and `/talk` shows a popup with a
    `wa.me` link after a successful reservation.
  - **Drafted 2026-10-04, not yet applied live: v6 stops asking for the number.** The prompt no longer asks
    verbally for a WhatsApp number. The address is taken from the caller's own account instead: the portal saves
    it once in `/settings`, the mock's declare route already falls back to that saved number keyed by
    `user_contact`, and the voice bridge already injects the signed-in caller's email into the first turn as
    `[caller: <email>]`. A new `CALLER` paragraph in the prompt tells the agent to read that prefix and pass it as
    `user_contact`, so nothing is asked and nothing is guessed. `docs/agenticorg/agent-spec.md` carries the new
    wording; the live agents still run the previous wording until the pause → `PATCH system_prompt_text` → resume
    cycle is run (v6-dev first, then v6).
  - **Drafted 2026-10-04, not yet applied live: a ceiling that cannot win is explained, not reported as an
    error.** The mock now refuses a bid whose `max_price_paise` is below the cheapest *acceptable* slot (#35), so
    the prompt gained a matching branch in STEP 4.3: that refusal is not a technical failure — release the mandate,
    say plainly the maximum is under the cheapest slot they would take, and ask for a higher one. The same prompt
    revision documents `min_price_per_person_paise` on `get_release`.
- **Fixed 2026-10-03: "The window opens at 11:30 AM IST on 9 October."** `opens_at_ist` is now a mock-computed
  field on both release routes (`mock_server/app.py` `opens_at_ist`), so the conversion is no longer the model's
  arithmetic; the prompt still needs to be told to read and repeat it rather than compute its own (live, open).

## 3. Pool and mandate correctness (mock side)

**Fixed 2026-10-03** (`docs/testing.md`, "L09's mock caveat, fixed"): `declare_interest` now accepts
`mandate_id`/`authorization_id` and keys the fallback `declaration_id` on it, so two different callers' bids on the
same release no longer collide or inherit each other's mandate. v6's prompt passes the authorization id
`create_mandate` returned; relinked to a new connector (`mcp_kirro_all_v23`) to pick up the schema change. Verified
live with two concurrent threads on `rel_0002` — both bids survived with their own `mandate_id`. `v4` (retired) and
`Kirro Allocator` were not touched and still key on `(run, release)` alone; this only matters for the Allocator if
it ever carries concurrent per-release traffic, which it does not (one release at a time).

**Fixed 2026-10-03** (#12 item 3): the catalogue fixture's dates are now seeded relative to the reset's own clock
(`mock_server/state.py` `_seed_domain`, `_FIXTURE_ANCHOR`/`_SEED_LEAD`) rather than pinned to a calendar date, so a
fresh run's releases are open for ~27h regardless of when the reset happens. `POST .../declarations` now refuses a
closed release with 409 `POOL_CLOSED` (`declarations_open` check in the handler).
**Verified live 2026-10-04 (issue #25):** asked `v6-dev` about a release closed on purpose for this check
(`ev_tennis`/`rel_0005`, `opens_at` already past, created directly against the live mock's `default` run — left in
place, no delete route exists for events/releases), 2/2 distinct phrasings got the same honest, specific refusal:
*"There is no open booking window for tennis on 12 October. The available date is Monday, 5 October. Would you
like to proceed with this date?"* — names the event, the date, states plainly there is no window, and offers the
real alternative with its own `weekday` field. This fires from the STEP 2 lookup-time `declarations_open` check,
not a live `POOL_CLOSED` 409 from `declare_interest` itself — by design, v6's own pre-check means it should never
reach that 409 in a normal single-turn conversation (only a mid-conversation race would do it, not reproducible
from a single live-chat call). **Residual:** one throwaway event (`ev_0002`, "Padel Court" — the model refused to
recognize "padel" as a supported event at all, a separate behavior quirk not pursued here) and one extra closed
release on the real `ev_tennis` (`rel_0005`, used for this check) are now permanently in the `default` run's
catalogue — no `DELETE` route exists for events or releases to clean them up.

**Fixed 2026-10-03** (#12 item 6): a second `declare_interest` call with the same `declaration_id` is now a no-op —
the stored bid is not overwritten, and the response carries `duplicate: true` so a caller (and L09) can tell a retry
from a first success (`tests/test_mock_server.py::test_declare_pool_second_call_with_same_declaration_id_is_a_no_op`).

## 4. Conversation quality

- **Fixed 2026-10-04: Hinglish mirroring (issue #17), verified live on production `v6`.** L03 ("Shanivaar ko court
  chahiye, char log") was understood correctly but answered in English, inconsistently (one live re-run before this
  fix: 1 Hinglish / 2 English replies across 3 fresh threads). Landed a description-only rule (no worked example,
  per the prior failure mode where a literal example got copied verbatim into English conversations) on
  `Kirro Declare v6-dev` first: **v1** (asymmetric — a reminder near the top of the prompt reinforced the
  Hindi/Hinglish-triggering direction twice while the English-only direction appeared once, weakly) fixed L03
  (3/3 Hinglish) but **broke L10** ("badminton or tennis, whichever", pure English) 2/3 of the time into a Hindi
  reply — caught by re-running L10 as the regression check the plan called for, not shipped. **v2** (symmetric:
  equal, explicit weight on both "Hindi in → Hinglish out" and "English in → English out", decided fresh every
  turn) re-tested clean: 3/3 L03 Hinglish, 3/3 L10 English, on `v6-dev`. Promoted via the documented
  pause → `PATCH system_prompt_text` → resume cycle (`platform-map.md` §11) onto the active `6596b872-…` agent;
  confirmed live on production immediately after resume (L10 English, L03 Hinglish, both correct). Separately
  observed, not fixed here (out of scope for #17): L03's event-ambiguity and date-resolution handling were
  themselves flaky across samples even before this change — worth its own issue if it recurs.
- **Verified live 2026-10-04 (issue #18): time-window filtering works.** No eval case had ever given v6 a time
  window ("7 to 9 am"), so slot filtering (`acceptable_slot_ids`) was unexercised against the live agent — the
  mechanism itself was already covered at the allocator level
  (`tests/test_allocator.py::test_time_constraint_hard_filter`). Ran a full declaration live against `v6-dev`:
  "badminton, 5 October, between 7 and 9 am, 2 people, Rs 300 per person" on `rel_badminton_sat` (slots at
  07:00, 08:00 and 18:00) → read-back correctly kept "between 7 and 9 am" → confirmed "yes" → the resulting pool
  entry (`GET /venue/releases/{id}/declarations`, ground truth per this issue's own suggested check) carries
  `"acceptable_slot_ids":["bd_0700","bd_0800"]` — exactly the two slots inside the stated window, correctly
  excluding the 18:00 slot. No prompt change needed; the agent already does this correctly.
- **Fixed 2026-10-04: waitlist ordering verified live end to end for a multi-bid release (issue #19).** Previously
  only single-bid releases had gone through the allocator-trigger bridge for real (ADR-018). Verified directly
  against the live mock (`api-kirro.upayan.dev`, dedicated run `issue19-verify` — isolated from `default`, no cleanup
  needed): created an organiser/event/release with one slot at capacity 1, seeded 4 `declare_interest` bids (one
  with `allocations_last_30d: 5`, three with `0`), read the pool back exactly as the Allocator's `list_pool_entries`
  tool would, and called `/allocator/draw` with those bids as its body (the same call the "Kirro Allocator" agent
  makes; see `mock_server/app.py` `allocator_draw` — bids come from the caller, not auto-read from the pool).
  Result, reproduced twice with the same deterministic seed: the bid with 5 prior allocations (fairness weight 1/6)
  waitlisted last, behind both bids with 0 prior allocations (weight 1) — `tests/test_allocator.py`'s weighted-
  permutation ordering holds against a real release's pool, not just unit-level fixtures. `rel["drawn"]` flipped to
  `true` as a side effect, confirming the bridge's own idempotency check (`candidate_releases` in
  `allocator_bridge/run_once.py`) would correctly drop this release from its next pass.
- **Open defect found 2026-10-04, agent-hop leg of issue #19: the live "Kirro Allocator" chat run produced an
  inconsistent result on a real multi-bid draw.** With AgenticOrg login now available, ran the actual missing
  piece above: created `rel_0007` (capacity-1 slot) in the `default` run with a 90s declare window, seeded 3 real
  `declare_interest` bids with live mandates, waited for the window to close, then sent the exact
  `allocator_bridge.run_once.TRIGGER_MESSAGE` text to "Kirro Allocator" over `/api/v1/chat/query` — 3 attempts
  with that exact wording all got the platform's generic "No agent was able to answer that query" router fallback
  (confidence 0, no `hitl_trigger`); a trivial "hello" to the same agent_id answered normally in between, so this
  was not a dead agent. A rephrased trigger ("Please draw and settle all bids for the release with id rel_0007
  now.") went through and the agent replied that all 3 declarations were **Waitlisted**, mandates released.
  Checking the mock directly after: `rel["drawn"]` is `true` (a real draw ran) but the slot's `capacity` dropped
  from 1 to **0** while **all three mandates show `RELEASED`**, not one `CAPTURED` — i.e. something held (and
  never released) the one slot's capacity on behalf of a winner, then that winner's own mandate got released
  along with the two genuine losers', so nobody is actually booked and the slot is now permanently stuck at
  zero capacity for this release (no booking record, no `release_hold` to undo the leak). This reproduces the
  shape of the already-documented platform bugs (#15 tool-call argument corruption; #16 the Workflow trigger
  executing zero steps) rather than anything in this repo's code: `mock_server/app.py`'s `allocator_draw`,
  `create_hold`, `execute` and `release_hold` are exercised correctly in isolation by `tests/test_mock_server.py`
  and by this issue's own mock-only check above — the fault is in the agent's own multi-step tool orchestration
  (hold → capture → confirm for the winner) on the live platform, not reachable or fixable from here. Needs the
  same `agenticorg:admin` run-trace access #15/#16 already ask for. Filed as its own issue, #37.
- **Fixed 2026-10-04: weekday/opens_at_ist/min_price_per_person_paise wired into v6's prompt (issue #24),
  verified live on production `v6`.** Both release routes already carried the mock-computed `weekday` (the model
  got "Wednesday, 11 October" wrong computing its own) and `min_price_per_person_paise` (so the mock, not the
  model, can tell a bidder their ceiling is below every slot); the prompt didn't yet tell v6 to read and repeat
  them. Added on `v6-dev` first: (1) the `get_release` tool description now names `weekday` and `opens_at_ist` as
  already-computed, never-recompute-yourself fields; (2) a new STEP 2 bullet fires a proactive ceiling warning
  against `min_price_per_person_paise` *before* attempting `create_mandate`, instead of only reacting to a failed
  `declare_interest`; (3) the STEP 3 read-back states the release's own `weekday` field instead of the prior
  "never state a weekday" workaround; (4) STEP 4's final confirmation reads `opens_at_ist` verbatim instead of
  asking the model to convert `opens_at` itself. Live-verified on `v6-dev`: a ceiling of Rs 100 against a release
  whose cheapest slot was higher got an immediate warning with **zero tool calls** (no wasted `create_mandate`);
  a full declaration for `rel_tennis_sat` read back "Tennis on Monday, 5 October..." — the weekday matched the
  release's own field exactly. (The final-confirmation `opens_at_ist` leg was not separately exercised — it needs
  a caller with a saved WhatsApp number, an orthogonal prerequisite the existing flow already gates on; the fix is
  the same verbatim-field mechanism as the weekday case, which did verify.) Promoted via pause/PATCH/resume onto
  the active `v6`; L10 regression-checked clean (still correct, still English) immediately after.
- **Verified 2026-10-04: interruption replies already correct (issue #20), no prompt change needed.** The
  2026-10-03 bug report ("No problem. Let me know when you're ready…" instead of re-asking the open question) did
  not reproduce: 4/4 live samples (3 on `v6-dev`, 1 on production `v6`) — send a partial declaration ("tennis, 4
  people"), then "wait, sorry" on the same thread — repeated the exact open question verbatim
  ("Which date do you want, and what is the most you'll pay per person?...") with no generic filler at all. The
  existing STEP 1(d) rule ("repeat only what is still open, in one short sentence") already covers this; whatever
  regressed it on 2026-10-03 is gone, possibly incidental to a later prompt edit. No action taken.

## 5. Operational

- **Done 2026-10-04: `Kirro Declare v6-dev` kept as the permanent test bed, not deleted.** Explicit decision
  (issue #21): prompt work on v6 is still open (Hinglish mirroring #17, interruption re-asks #20, reading the
  mock-computed `weekday`/`opens_at_ist`/`min_price_per_person_paise` fields #24), and each of those needs the
  pause → `PATCH system_prompt_text` → resume cycle on v6-dev first (§1 "How to test any prompt change"). Revisit
  once all three land and no further prompt iteration is planned.
- **Fixed 2026-10-03: `/__admin/*` answered on the public mock URL.** `MOCK_ADMIN_KEY`, when set, now gates every
  `/__admin/*` call behind a matching `X-Admin-Key` header (`mock_server/app.py` `_admin_key_denied`,
  `docs/connectors.md`). Still open: the key itself has not been provisioned (needs a human with `sops`/`age` to add
  a `kirro-mock-admin` Secret in the cluster repo, same ksops pattern as `kirro-voice`) — until then this is a no-op
  by design, so the surface is still open on the live cluster.
- **Fixed 2026-10-04: `rel_0002`/`rel_0003` test pools cleared (issue #21).** `rel_0001` and `rel_tennis_sat` stay
  untouched — drawn for real by the allocator-trigger bridge's own live verification (`docs/testing.md`, "The
  allocator-trigger bridge"), `BK-0001`/`BK-0002` `CONFIRMED`, genuine demonstrations, not contamination. `rel_0002`
  (6 declarations, mandates `auth_0016`–`auth_0023`) and `rel_0003` (4 declarations including the stray `probe_b`,
  mandates `auth_0011`/`auth_0015`/`auth_0016`/`auth_0019`) held test pool entries and active mandates from prompt-
  iteration sessions. Cleared via `DELETE /venue/releases/{id}/declarations/{decl}` then
  `POST /pinelabs/mandates/{id}/release` against the live mock (`api-kirro.upayan.dev`); both pools confirmed empty
  afterward. Both releases are still `declarations_open: true, drawn: false`, so they will accept fresh bids
  normally — this only removed the stale ones.
- **`v4`'s stored accuracy looked stale** (0.691 matched the running mean at 18:25Z, not the full mean 0.663).
  `POST /agents/{id}/retest` probably recomputes it; untested, and not worth running on v6.
