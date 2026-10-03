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
- **Cumulative transcript re-sends.** On v4, 14 user turns were the previous turn plus more words ("solah ek" →
  "solah ek ek din" → …), each a scored turn and a repeated read-back. Fix in `voice_bridge/agenticorg_llm.py`: send
  only the newest user message, skip an exact repeat, send only the new suffix of a growing one; log every skip.
  Check first that LiveKit keeps one `ChatMessage.id` while a late transcript is appended (INFERENCE).
- **Questions before any event is named** (greeting, "what can you do", ambiguous "court"). These are legitimate
  and must stay; they are why chat traffic will hover near, not far above, 0.80.

Do not chase the score with padded replies, gratuitous tool calls or filler conversations (`docs/testing.md` lists
the rejected levers).

## 2. Promises the system cannot keep yet

- **"You will get a WhatsApp message with the result after the draw."** v6 says this on every successful pool
  entry, but nothing sends it: the Window Allocation Workflow executes zero steps (`platform-bugs.md` Bug 2), and the
  pool entry carries `user_contact: null`, so even a working Workflow would have no one to message. Options: capture
  a contact in the declaration (the bridge knows the signed-in email; the chat panel does not), or change the closing
  line to say the result follows the draw without naming a channel. The second is a one-line prompt change.
- **"The window opens at 11:30 AM IST on 9 October."** Correct today (06:00Z + 5:30), but the conversion is the
  model's arithmetic. A mock-provided `opens_at_ist` field would remove it; low priority.

## 3. Pool and mandate correctness (mock side)

**Fixed 2026-10-03** (`docs/testing.md`, "L09's mock caveat, fixed"): `declare_interest` now accepts
`mandate_id`/`authorization_id` and keys the fallback `declaration_id` on it, so two different callers' bids on the
same release no longer collide or inherit each other's mandate. v6's prompt passes the authorization id
`create_mandate` returned; relinked to a new connector (`mcp_kirro_all_v23`) to pick up the schema change. Verified
live with two concurrent threads on `rel_0002` — both bids survived with their own `mandate_id`. `v4` and
`Kirro Allocator` were not touched and still key on `(run, release)` alone; this only matters if either carries
real concurrent traffic, which neither does (v4 is being retired, the Allocator runs one release at a time).

Still open:

- **No server-side refusal for a closed release.** `declarations_open` tells the agent, but the REST pool route still
  accepts a bid after `opens_at`. It was left out because every seeded fixture release is past its window; once the
  seed computes dates relative to the reset time (`mock_server/state.py` `_seed_domain`), add `409 POOL_CLOSED`.
- **Duplicate declarations return `DECLARED`, not a duplicate marker**, so L09's "second call is a no-op" cannot be
  observed from the agent's side.

## 4. Conversation quality

- **Hinglish mirroring is weak.** L03 ("Shanivaar ko court chahiye, char log") was understood correctly but answered
  in English. An earlier attempt with a literal Hinglish example reply made the model copy that reply into English
  conversations, so any fix needs a description-only rule and a re-run of L03 and L10 together.
- **Time windows are untested.** No case gives a window ("7 to 9 am"), so slot filtering by window
  (`acceptable_slot_ids`) has not been exercised on v6. Add a case.
- **Weekday names were dropped from the read-back** because the model got them wrong ("Wednesday, 11 October"). If
  weekdays are wanted back, have the mock return them with the release instead of asking the model.
- **The "slots cost more than your maximum" warning was removed** after the model raised it when the ceiling was
  above the cheapest slot. If it is wanted, compute it in the mock (e.g. a `min_price_per_person_paise` field) and let
  the prompt only repeat it.
- **Interruption replies are generic** ("No problem. Let me know when you're ready…") rather than re-asking the open
  question. Acceptable, but L04 says "repeats only the open question".

## 5. Operational

- **Retire v4** after v6 has carried real voice traffic cleanly: pause → retire (keep it, do not delete, so its
  history stays as evidence). Delete `Kirro Declare v6-dev` once no more prompt work is planned, or keep it as the
  permanent test bed.
- **`/__admin/*` answers on the public mock URL** (`https://api-kirro.upayan.dev/__admin/state` returned 200). Anyone
  can arm scenarios or reset state during a demo. Restrict it at the ingress or require a header.
- **Eval data left in run `default`:** pool entries on `rel_0002` and `rel_0003` and their active mandates. Clear them
  (`DELETE /venue/releases/{id}/declarations/{decl}` and `POST /pinelabs/mandates/{id}/release`) before a demo that
  runs the allocator, or the draw will include test bids.
- **`v4`'s stored accuracy looked stale** (0.691 matched the running mean at 18:25Z, not the full mean 0.663).
  `POST /agents/{id}/retest` probably recomputes it; untested, and not worth running on v6.
