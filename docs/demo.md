# Demo — Round 3 recording plan

**The video and the written answers are two separate submissions.** This file and `demo-script.md` are only about
the video; it has to stand on its own without anyone reading the answers, so nothing in it says "as explained in the
write-up". The answers live in `submission/round-3-answers.md` and are not narrated here.

Three files, three jobs:

- **`demo-script.md`** — the shooting script. Scene by scene: the page on screen, the exact words spoken, and the
  frame that has to be visible. Shoot from that.
- **this file** — the operational plan behind it: pre-flight, screen layout, what each take has to prove, what must
  never be filmed, and what to do when the platform misbehaves mid-take.
- **`submission/round-3-answers.md`** — the separate written submission.

The brief: record the screen while the agent runs **on the Pine Labs platform**, from the first thing that happens to
the moment the outcome is achieved, then run it again with **at least two different human inputs** and show how the
output changes.

Everything below is grounded in what has actually run. Every beat carries a live precedent or is marked as unproven.
**Read `## Do not demo` before planning a single shot** — three paths in this system are currently broken in ways that
would produce a wrong-looking or wrong-in-fact recording.

## What the recording has to show

| Brief requirement                                                     | How KIRRO satisfies it                                                                                                                                                           | Beat          |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| Agent runs and decides inside the platform                            | `Kirro Declare v6` (`6596b872-abb5-465a-87d3-fff8de17536d`) and `Kirro Allocator` (`5591e57a-79f9-4b30-a95e-0b910a467ce3`), both `active` on `agenticorg.hackathon.pinelabs.com` | all           |
| Every voice input and reply goes through Gnani                        | Gnani Prisma STT + Timbre TTS (`timbre-v2.5`, voice `Kaveri`, `en-IN`) inside the LiveKit worker (ADR-016/017)                                                                   | T1-2          |
| Delhivery mocked with its documented endpoint names                   | `GET /delhivery/c/api/pin-codes/json/`, `POST /delhivery/api/cmu/create.json`, `GET /delhivery/api/v1/packages/json/`                                                            | T4            |
| Pine Labs real where the platform offers it, mocked where it does not | real UAT order via `pinelabs-python` from the mock; mandate hold/release mocked (no such primitive exists)                                                                       | T1-5, caption |
| Every other connector is the real tool                                | `whatsapp_kirro` → real WhatsApp Business `+91 81673 12268`                                                                                                                      | T1-6          |
| A teammate plays the user through a real tool                         | the caller speaks into `/talk` and receives the result on a real handset over WhatsApp                                                                                           | T1, T1-6      |
| Mock returns different responses including bad ones                   | `POST /__admin/scenario`, 10 injectable failures, armed from `/admin` on camera                                                                                                  | T3            |
| Agent handles them                                                    | the agent releases the mandate and says what actually happened                                                                                                                   | T3            |
| Two further runs with different human inputs                          | Take 2 ("no" after a correction), Take 3 (Hinglish + an ambiguous price)                                                                                                         | T2, T3        |
| The mechanism is not a toy                                            | a 10-place stadium concert at Rs 4,500, a society court at Rs 250, a club tennis slot, and an F1 paddock pass that physically ships — one agent, one mechanism                   | T1, T3, T4    |

## Pre-flight (do this before any recording, not on camera)

1. **Reset the run.** `/admin` → Demo controls → "Clear this run", or `POST /__admin/reset {"run_id":"default"}`.
   Fixture releases are seeded relative to the reset's own clock, so a fresh run gives you releases that stay open for
   about 27 hours. This also clears `ev_0002` ("Padel Court") and the closed `rel_0005` out of shot — there is no
   `DELETE` route for events or releases, so a reset is the only way to clean the catalogue.
1. **Confirm the scenario is disarmed.** `POST /__admin/scenario {"run_id":"default","target":"*","scenario":"success"}`.
1. **Confirm the concert is findable by name.** The agent resolves an event from free text. Portal-created events get
   opaque sequential ids (`ev_0003`), so this depends on the release listing carrying the event's name and aliases —
   shipped as part of this round's work. After creating the concert, ask the agent "what concerts are open?" in the
   platform chat panel and confirm it finds it. **If it does not, the mock on the cluster is older than the fix**:
   check that `main` has rolled out before shooting.
1. **Save the caller's WhatsApp number** at `https://kirro.upayan.dev/settings`. `declare_interest` refuses a bid
   without one (400), and the agent will correctly refuse and point at Settings — a true behaviour, but not the
   happy path.
1. **Open the 24-hour WhatsApp window.** From the handset that will be on camera, send one message to
   **+91 81673 12268**. The Business API only permits freeform text inside a window the user opens; without it the
   result message never arrives. This is a forced ordering, not a nicety.
1. **Check both agents answer.** Send "hello" to `Kirro Declare v6` in the platform's chat panel. If you get
   *"No agent was able to answer that query"*, that is the platform's router fallback (see
   `## Known hazards`), not a dead agent — wait and retry.
1. **Warm the browser.** Load `/talk`, grant the microphone permission, close the tab. The permission prompt is not
   part of the story and the capture path has never been exercised by a human (issue #27) — find that out in
   rehearsal, not in the take.
1. **Stage the windows.** See `## Screen layout`.

## Screen layout

Record one screen at 1920x1080. Two arrangements, switched between takes:

- **Conversation layout** — browser full-screen on `https://kirro.upayan.dev/talk`, handset on camera (or screen-
  mirrored) in a corner for the WhatsApp beat.
- **Evidence layout** — browser split: left `agenticorg.hackathon.pinelabs.com` (agent detail / Audit Log), right a
  terminal tailing the mock's own request log:
  `kubectl logs -f deploy/kirro-mock -n kirro | grep -E 'mcp\.|target'`.

Have these tabs open throughout, in this order: `/` · `/talk` · `/dashboard` · `/admin` · AgenticOrg agent page ·
Grafana (`https://grafana.upayan.dev`, dashboard "KIRRO (voice channel + agent)").

## Take 1 — the full run, first event to outcome (scenes 0–5, target 4–5 min)

The story: **a stadium concert puts ten front-standing places up, and four thousand people want them.** The scale is
the point — this is the case where first-come-first-served most obviously fails, and where blocking money instead of
taking it matters most. The society badminton court and the club tennis slot appear later (takes 3 and 4) to show the
same mechanism at Rs 250 a head.

**Create the concert live on `/organiser`, not with the quick-demo button.** The button picks a template at random,
which is not shootable, and creating it by hand is a better shot anyway: it shows the organiser surface and makes the
point that the organiser picks a *rule*, not a winner.

| #    | Shot                           | What happens                                                                                                                                                                                                                          | On-screen proof                                                                                     |
| ---- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1-1  | `/` hero                       | 35 s. "Booking scarce slots shouldn't reward whoever clicks fastest." Scroll past `DrawVisualizer` and the live inventory pulled from the mock.                                                                                       | the listing cards are live mock data, not markup                                                    |
| 1-2  | `/organiser` → **New event**   | `Stadium Concert (Front Standing)`, published.                                                                                                                                                                                        | the event appears with its `published` badge                                                        |
| 1-3  | `/organiser` → **New release** | the concert · **Draw** · today · opens in ~6 min · slot `Front Standing, 20:00` · **10 seats** · **Rs 4,500**.                                                                                                                        | the release row renders as `Draw · 0 in the draw`                                                   |
| 1-4  | `/talk` → start                | token minted server-side, browser joins `wss://voice-kirro.upayan.dev`, the worker speaks a fixed greeting, the call id `call_<12hex>` appears beside the transcript.                                                                 | state label goes Connecting → Listening; call-id badge                                              |
| 1-5  | **the declaration, spoken**    | see the script.                                                                                                                                                                                                                       | live transcript, bar visualiser                                                                     |
| 1-6  | the read-back                  | agent states event, weekday, date, group, minimum, ceiling and the reserve total, then "Shall I go ahead? Please say yes or no."                                                                                                      | the weekday comes from the release's own `weekday` field — the agent is forbidden to compute one    |
| 1-7  | "yes" → money                  | `create_mandate` fires **alone**, returns an authorization id and `ACTIVE`; only then `declare_interest`.                                                                                                                             | terminal shows `mcp.create_mandate` then `mcp.declare_interest`, in that order, never parallel      |
| 1-8  | the `wa.me` popup              | fires on the agent's "reserved, not charged" line; tap it, confirm the opening message.                                                                                                                                               | popup with the Business number pre-filled                                                           |
| 1-9  | `/admin`                       | Draw entries +1, Captured still 0; the Releases table shows Entries = 1 for the concert.                                                                                                                                              | stat tiles move                                                                                     |
| 1-10 | window closes                  | `/events/<id>` countdown hits **"Window closed — the draw runs within 5 minutes."**                                                                                                                                                   | the countdown is the honest clock                                                                   |
| 1-11 | the draw                       | the `kirro-allocator-trigger` CronJob (every 5 min) finds the closed, undrawn release and asks `Kirro Allocator` to settle it. Force it on camera with `kubectl create job --from=cronjob/kirro-allocator-trigger draw-now -n kirro`. | terminal: `allocator.draw` → `create_hold` → `get_hold` → `execute` → `confirm_booking` → `release` |
| 1-12 | the outcome                    | `/dashboard` shows the booking row with `BK-####`, hold id and payment id; Payments shows SUCCESS.                                                                                                                                    | the booking reference is the outcome                                                                |
| 1-13 | the handset                    | the WhatsApp result message arrives on the real number.                                                                                                                                                                               | real phone, real message                                                                            |

### The spoken lines (Take 1)

Full narration is in `demo-script.md`; these are the facts the caller's turns must contain.

> **Caller:** "I want the concert tonight. Front standing. Four of us, but three would still work. I'll pay up to four
> and a half thousand rupees each."

Expected reply shape (this read-back template is in the prompt verbatim):

> **KIRRO:** "Stadium Concert on [weekday], [date], any slot, 4 people, minimum 3, up to Rs 4,500 per person, so I
> will reserve Rs 18,000, not charge it. Shall I go ahead? Please say yes or no."

> **Caller:** "Yes."

Expected: `create_mandate` with `amount_value: 1800000` (4 × 4,500 × 100), then `declare_interest`, then a closing
message that says the money is reserved and not charged, names the release's own `opens_at_ist` verbatim, and says
nothing about WhatsApp or a phone number — the `/talk` page's own popup is what prompts the caller to send the one
opening message.

**Live precedent:** the same chain ran on 2026-10-03 at a smaller amount — `create_mandate` 120000 ACTIVE →
`declare_interest rel_0002` DECLARED (`docs/testing.md:280`); the single-bid draw chain produced `BK-0001` and
`BK-0002` CONFIRMED through the bridge (`docs/testing.md:366-384`); WhatsApp delivery to a real handset was verified
at `BK-0003` (`docs/testing.md:315-328`).

**Why a concert is safe to shoot despite the capacity being 10:** the draw is only dangerous with **more bids than
capacity** (issue #37). One bid against ten places is the proven single-bid path. Do not seed extra bids to make it
look contested.

## Take 2 — different human input: she says no (scene 6, target 60–90 s)

A fresh call against the **same concert release**, so only the human changes:

> **Caller:** "Concert tonight, two of us, up to three thousand each."
>
> *(read-back for 2 people)*
>
> **Caller:** "Actually make it four of us."
>
> *(the agent applies the correction immediately and reads back again — "actually" is a correction signal in the
> prompt. A different number with **no** correction signal would instead get "you said two earlier, do you want to
> change it to four?", because a misheard number and a changed mind sound identical over a phone line)*
>
> **KIRRO:** "... Shall I go ahead? Please say yes or no."
>
> **Caller:** "No."

**What must be visible:** the group size changed on the correction *without* a confirmation question, and after "no"
the mock's log contains **no `create_mandate` and no `declare_interest` at all** for that thread. Cut to the terminal
and show the absence. That is the point: declining costs the user nothing, which is the only reason declaring
interest is a reasonable thing to ask a person to do.

**Live precedent:** L05 on v6, 2026-10-03 — "actually make it Sunday" applied at once, no open tennis window on
Sunday so it offered 10 October, "no" → cancelled, no money tool in the log (`docs/testing.md:271`).

## Take 3 — different human input: Hinglish, an ambiguous price, and a failing rail (target 2–3 min)

Three changes in one take, because they compound.

**3a — ambiguous price.** Open with a range:

> **Caller:** "Tennis court Saturday, two of us, budget eight to ten thousand, ideally eight."

Expected: the agent stores **nothing** for the price and asks *"What is the single maximum you will pay per person?"*
Neither 8,000 nor 10,000 appears anywhere in the reply, and no tool is called. (L01, passed on every prompt version
since v0 — `docs/testing.md:266`.)

**3b — Hinglish.** Switch language mid-conversation:

> **Caller:** "Shanivaar ko court chahiye, char log."

Expected: the whole reply in Hinglish, Roman script; "court" is treated as ambiguous (badminton *and* tennis exist),
so it asks which one **and** the ceiling in one question, keeping Saturday and 4. The language is decided fresh from
the newest message every turn — an English message right after this one must get an English reply.

**Live precedent:** the symmetric language rule landed 2026-10-04 after an asymmetric first attempt fixed L03 3/3 but
broke L10 into Hindi 2/3 and was **not shipped**. Final rule verified 3/3 Hinglish on L03 and 3/3 English on L10
(`docs/agenticorg/declare-v6-notes.md:126-139`). Say this out loud in the voice-over: the regression check is why the
first fix was thrown away.

**3c — the rail fails.** Before the "yes", on camera: `/admin` → Demo controls → Target `pinelabs.create_mandate`,
Scenario `insufficient_balance` → "Set scenario". Then say "yes".

Expected: `create_mandate` returns **402 INSUFFICIENT_BALANCE**, the mock's state shows `mandates: 0`, and the agent
says the amount could not be reserved and offers to try again or cancel. It **never** says "reserved" and never calls
`declare_interest`.

**Live precedent:** L06, 04:59 on 2026-10-02 (`docs/testing.md:278`) and again on v6 (`docs/testing.md:272`).

**Say on camera while arming it:** scenario control is out of band. The agent's request carries only its business
payload and an `X-Run-Id` header; no response ever names a scenario; scenarios are deliberately not reachable from the
MCP surface at all. The agent cannot know it is being tested.

**Disarm immediately after the take:** Target `*`, Scenario `success`.

## Take 4 — optional: Delhivery, for the physical-pass event (target 45 s)

Only if the video has room. Use an F1-paddock-pass style event where a physical pass ships after `CONFIRMED`.
Delhivery is post-confirmation fulfilment, never in the booking loop (ADR-004).

Show all three endpoints with their documented names on screen:
`GET /delhivery/c/api/pin-codes/json/?filter_codes=110001` → `delivery_codes[].postal_code{pin, pre_paid, cash, pickup, district, state_code}`; `POST /delhivery/api/cmu/create.json` with `format=json&data=...` →
`{success, packages[{waybill, refnum, status}], rmk}`; `GET /delhivery/api/v1/packages/json/?waybill=...` →
`ShipmentData[].Shipment{AWB, Status{Status}}`.

Then show a bad one: an unknown pincode returns `200 {"delivery_codes": []}` — an empty list, exactly as a real lookup
would, not an error. A duplicate `order` returns `rmk: "Duplicate order id"`.

**Caption honestly:** the paths and the serviceability response field names match a read of
`delhivery-express-api-doc.readme.io`; `filter_codes` is community-sourced; the create and track **response** bodies
are KIRRO mock shapes and were not verified against the real API.

## Take 5 — the evidence montage (target 60–90 s)

Cut between, in this order:

1. **The mock's own request log** — `<run_id>.jsonl`, one line per request with `ts, request_id, path, target, scenario, request, response, status, latency_ms`, redacted. MCP invocations are logged with the arguments received
   **before validation**, so a refused call still leaves a trace. This is the primary verdict source for every eval in
   `docs/testing.md`; the agent's own words are not.
1. **`GET /__admin/state`**, or the `/admin` stat tiles that render it: mandates, holds, bookings, payments,
   `released_mandates`, captured and refunded paise.
1. **Grafana** — paste the call id from the `/talk` badge into the `call_id` box on the "KIRRO (voice channel +
   agent)" dashboard: the greeting, each turn's `thread_id`, latency, redacted query and answer, pipeline errors, and
   the close reason, end to end. Caveat on camera: Loki keeps 168 hours.
1. **AgenticOrg Audit Log** (`/dashboard/audit`), filtered to `declared_interest_booking` / `kirro_allocator`.
   **Caption required:** the tenant is shared across competition teams, so page 2 contains another team's agent. Filter
   on agent type, never trust row counts.
1. **The agent detail page** — `Kirro Declare v6`, active, and the cost tab: monthly cap $200.00, current spend
   $0.8765, 2,337,921 tokens, 65 tasks, 0.4% utilisation. The whole declare leg has cost under a dollar.

## Do not demo

Each of these would put something false or broken on camera.

1. **The native "Kirro Window Allocation" Workflow.** It is defined (7 steps, `trigger_type: schedule`, cron
   `5 6 * * *`, `is_active: true`), the trigger fires, and it executes **zero steps** — no connector request at any
   step and no Audit Log event at all, every run. The same agent driven by chat executes every tool correctly. Six
   candidate causes were tested and ruled out; `GET /api/v1/workflow-runs/{id}` is OAuth-gated (401) so the reason is
   unreadable. Issue #16. **Show `allocator_bridge/` instead and name the Workflow as the platform bug it is.**
1. **A live multi-bid contested draw.** On 2026-10-04 a capacity-1 release with three real bids was drawn through the
   chat-driven allocator: afterwards `drawn: true`, but the slot's capacity had gone 1 → 0 while all three mandates
   read `RELEASED` and none `CAPTURED`, with no booking record and no `release_hold`. Nobody was booked and the slot
   is permanently stuck at zero. Each mock route is correct in isolation and the draw ordering was verified by calling
   `/allocator/draw` directly — the fault is in the agent's live multi-step orchestration. Issue #37. **Record the
   single-bid path, which has `BK-0001`/`BK-0002` behind it.**
1. **The literal `allocator_bridge` trigger sentence.** "Run the allocation for release_id {id}: draw its bids and
   settle every one." hit the router's *"No agent was able to answer that query"* fallback 3/3 times, while a trivial
   "hello" to the same agent answered in between. If a trigger must be sent by hand on camera, use the rephrased form.
1. **"padel".** The model refuses to recognise it as a supported event. `ev_0002` exists in the `default` run and
   there is no delete route — reset before recording.
1. **`rel_0001` and `rel_tennis_sat`.** Already drawn, carrying the genuine `BK-0001`/`BK-0002` evidence. Leave them.
1. **`/dashboard/observatory`.** It displays a canned "Invoice Processing Pipeline" demo with a fake live feed,
   naming neither KIRRO agent. Never cite it as evidence of a KIRRO run. `/dashboard/enforce-audit` shows 0 entries.
1. **A declaration from a caller with no saved WhatsApp number.** Correct behaviour (release, then point at Settings),
   but not the happy path.

## Known hazards during the shoot

| Hazard                                                             | Frequency observed                                                                                                                   | Plan                                                                                                                                                                                                                            |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Platform router answers *"No agent was able to answer that query"* | 3 of ~12 turns, **both** agents, not prompt-caused; over voice the caller **hears** it                                               | retake. Pre-record Take 1 rather than going live                                                                                                                                                                                |
| Tool-call arguments arrive null or corrupted                       | intermittent, per tool; `create_mandate` always lands, everything else fails most of the time with 1–30 min good windows (issue #15) | rehearse immediately before the take; if `get_release` starts returning garbage, wait for the window                                                                                                                            |
| Gnani TTS returns 500                                              | four consecutive failures observed 18:37Z, reply never spoken                                                                        | the portal shows "KIRRO is having trouble speaking right now" by design. Retake; or keep it and narrate it as an honest failure surface                                                                                         |
| Browser microphone capture                                         | **never exercised by a human** (issue #27)                                                                                           | rehearse it; the recording is itself the first real test                                                                                                                                                                        |
| Final transcript dropped at turn commit                            | observed live, Gnani emits no interim transcripts so LiveKit's fallback has nothing to use (issue #28)                               | if a turn vanishes, repeat it; do not silently cut                                                                                                                                                                              |
| Red "Below Floor" badge on the agent page                          | v6 sits at ~0.80–0.82; tool-less turns pull it under                                                                                 | have the explanation ready: the platform's per-turn confidence is mechanical — 0.85 once any tool has been attempted in the thread, else 0.60 for a reply ≤100 chars and 0.65 for ≥101. It is not a judgement about correctness |

## Fallbacks

- **Voice blocked or Gnani down:** continue the same declaration with the same agent in the platform's own chat
  panel, and report it as a finding. The agent is the same agent; only the channel changes.
- **CronJob slow:** `kubectl create job --from=cronjob/kirro-allocator-trigger draw-now -n kirro` and show the job
  logs.
- **Demo window timing:** the quick-demo release opens 3 minutes after the click and closes 3 minutes later. A single
  continuous take therefore needs ~6 minutes of dead air plus up to 5 for the CronJob. Either cut between 1-8 and 1-9
  with a visible clock, or seed the release by hand with a shorter window before recording.

## The rule that governs the whole shoot

A human may set a scenario, speak as the user, and trigger an external event. A human must **never** reason for the
agent. If the agent does the wrong thing on camera, that take is evidence, not a mistake to edit out — the written
answers already record every failure this system has had.
