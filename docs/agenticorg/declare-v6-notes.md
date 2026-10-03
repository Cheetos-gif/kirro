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
closed release with 409 `POOL_CLOSED` (`declarations_open` check in the handler). Still open: wiring this into v6's
prompt/error handling and a live re-check that the agent surfaces the refusal sensibly.

**Fixed 2026-10-03** (#12 item 6): a second `declare_interest` call with the same `declaration_id` is now a no-op —
the stored bid is not overwritten, and the response carries `duplicate: true` so a caller (and L09) can tell a retry
from a first success (`tests/test_mock_server.py::test_declare_pool_second_call_with_same_declaration_id_is_a_no_op`).

## 4. Conversation quality

- **Hinglish mirroring is weak (live, open).** L03 ("Shanivaar ko court chahiye, char log") was understood correctly
  but answered in English. An earlier attempt with a literal Hinglish example reply made the model copy that reply
  into English conversations, so any fix needs a description-only rule (e.g. "mirror the caller's register — if they
  mix Hindi and English, answer the same way, without a worked example to copy") and a re-run of L03 and L10 together
  on `Kirro Declare v6-dev` first. Requires live prompt-editing access; not actionable from this repo alone.
- **Time windows on v6 are untested (live, open — issue #18).** No eval case gives a window ("7 to 9 am"), so slot
  filtering by window (`acceptable_slot_ids`/`constraints.start_hour_min|max`) has never been exercised against the
  live agent — the mechanism itself is covered (`tests/test_allocator.py::test_time_constraint_hard_filter`). Needs a
  live eval case against the agent, not a mock-server change; blocked here on AgenticOrg login (never stored in this
  repo, `platform-map.md` §1).
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
  `allocator_bridge/run_once.py`) would correctly drop this release from its next pass. **Not covered:** the
  CronJob → AgenticOrg chat → "Kirro Allocator" agent hop itself (blocked on AgenticOrg login, as above) — this
  verifies the draw/waitlist mechanics the agent's call would trigger, not the agent's own tool-calling behaviour.
- **Fixed 2026-10-03: weekday names and the price-ceiling warning.** Both release routes now carry a mock-computed
  `weekday` (the model got "Wednesday, 11 October" wrong) and `min_price_per_person_paise` (the cheapest slot's
  price, so the mock — not the model — can tell a bidder their ceiling is below every slot). Still open: telling
  v6's prompt to read and repeat these instead of computing or guessing them (live).
- **Interruption replies are generic (live, open)** ("No problem. Let me know when you're ready…") rather than
  re-asking the open question. Acceptable, but L04 says "repeats only the open question"; needs a prompt change and
  a re-run, not a mock-server change.

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
