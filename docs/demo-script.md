# Demo video — final script

The shooting script. `demo.md` is the operational plan behind it (pre-flight, hazards, what must never be filmed).

**The video and the written answers are separate submissions.** This video has to stand on its own — nothing in it
says "as covered in the write-up".

**Open `demo-cue-card.html` on a second screen or a phone while you record.** It is this script reduced to cues,
one scene per card, colour-coded by presenter, with a running clock. Arrow keys move between cards, `F` filters to
one presenter's cards only.

## Who does what

| Role  | Who    | Owns                                                                                                                                                     | Screen                            |
| ----- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| **A** | you    | the product: `kirro.upayan.dev`, the organiser surface, `/talk`, `/admin`, the phone                                                                     | OBS scene `DESKTOP`, plus `PHONE` |
| **B** | Upayan | the platform: `agenticorg.hackathon.pinelabs.com` — the agents, their prompt, tools, connectors, audit trail — plus the mock's request log in a terminal | OBS scene `PLATFORM`              |

A hands to B at the moment the agent has to decide something, and B hands back once the platform has shown it. Keep
the handoffs explicit and short — "here's what the agent did with that" / "back to the product".

## OBS scenes to set up before you start

| Scene      | Sources                                                                                                                                                               |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DESKTOP`  | display capture, browser full-screen                                                                                                                                  |
| `PHONE`    | the handset, either screen-mirrored (scrcpy for Android, QuickTime for iPhone) or a camera on a stand. **Rehearse this one** — it is the shot most likely to go wrong |
| `PLATFORM` | Upayan's display capture (or a second browser profile signed into AgenticOrg)                                                                                         |
| `SPLIT`    | `DESKTOP` on the left, terminal tailing the mock log on the right: `kubectl logs -f deploy/kirro-mock -n kirro`                                                       |

**Runtime target: 8:30–9:30.** Two voices and a caller: **A** and **B** narrate, **C** is the caller (a teammate
speaking into the phone). Nothing in this script has a narrator explaining what the agent is about to decide — the
agent decides, then we show the log.

| #   | Scene                                                       | Presenter | Screen     | Runtime |
| --- | ----------------------------------------------------------- | --------- | ---------- | ------- |
| 0   | Cold open — the problem                                     | A         | `DESKTOP`  | 0:35    |
| 1   | An organiser puts a concert up for a draw                   | A         | `DESKTOP`  | 0:45    |
| 2   | This is the agent, on Pine Labs' platform                   | **B**     | `PLATFORM` | 0:50    |
| 3   | It's a phone product — install it                           | A         | `PHONE`    | 0:35    |
| 4   | The declaration, by voice, on the phone                     | A + C     | `PHONE`    | 1:40    |
| 5   | What the agent actually did                                 | **B**     | `PLATFORM` | 0:50    |
| 6   | The pool, from the organiser's side                         | A         | `DESKTOP`  | 0:25    |
| 7   | The window closes, the draw runs                            | **B**     | `SPLIT`    | 1:10    |
| 8   | The outcome, on her phone                                   | A         | `PHONE`    | 0:40    |
| 9   | Different input: she says no                                | A + C     | `DESKTOP`  | 0:50    |
| 10  | Different input: Hinglish, a vague price, a rail that fails | A + **B** | `SPLIT`    | 1:30    |
| 11  | The same agent, a very different event                      | A         | `DESKTOP`  | 0:40    |
| 12  | Evidence, and what is honestly broken                       | **B**     | `PLATFORM` | 1:00    |

______________________________________________________________________

## Scene 0 — Cold open (A, `DESKTOP`, 0:35)

**Screen:** `https://kirro.upayan.dev`. Scroll slowly through the hero, the allocation diagram and the draw
visualiser. Do not click anything.

> **A:** "A stadium concert puts ten front-standing places on sale. Four thousand people want them. Today those ten
> go to whoever's browser renders the Buy button first — which means they go to bots, to the fastest connection, to
> luck dressed up as fairness.
>
> KIRRO does something else. You *declare* what you want and what you'll pay. Your money is blocked, not spent. When
> the window closes, one seeded draw decides, once. Speed buys you nothing, because there's nothing to race for."

**Must be visible:** the hero line "Booking scarce slots shouldn't reward whoever clicks fastest", the draw
visualiser animating, and the live inventory cards — pulled from the mock, not hard-coded.

______________________________________________________________________

## Scene 1 — An organiser puts a concert up for a draw (A, `DESKTOP`, 0:45)

**Screen:** `/organiser`, signed in as an approved organiser.

> **A:** "This is the organiser's side. I'm creating the concert now, live — nothing seeded, nothing pre-baked."

**Actions, on camera, in this order:**

1. **New event** → `Stadium Concert (Front Standing)` → Status `published` → Create.
1. **New release** → the concert → **Draw** → Date: today → Opens: six minutes from now → Slot label
   `Front Standing, 20:00` → Starts: tonight 20:00 → Seats **10** → Price **4500**.

> **A:** "Ten places. A declare window that closes in six minutes, and a draw that runs the moment it does. The
> organiser never picks a winner — they pick a *rule*. Upayan, over to you: where does the agent actually live?"

**Must be visible:** the release row rendering as **Draw · 0 in the draw**.

______________________________________________________________________

## Scene 2 — This is the agent, on Pine Labs' platform (B, `PLATFORM`, 0:50)

**Screen:** AgenticOrg → Agents list → open **Kirro Declare v6**. Move through Persona, Prompt, Authorized Tools,
then the Connectors page.

> **B:** "KIRRO isn't a service we host that pretends to be an agent. It's a Virtual Employee on Pine Labs'
> AgenticOrg platform, and this is it — Kirro Declare, active, with a shadow twin we test every prompt change on
> before it ever reaches a caller.
>
> It has exactly six tools. It can look up a release, reserve money, enter the pool, cancel that entry and release
> the money. It **cannot** charge anyone, it cannot create a booking, and it cannot run the draw — a second agent
> does that, after the conversation is over. That split is deliberate: the platform's tool permissions are static,
> so the only way to enforce least privilege is to not grant the tool.
>
> And everything it touches goes through connectors. WhatsApp is the real WhatsApp Business connector. Speech is
> Gnani. Our four mocked surfaces come in as one MCP connector with eighteen tools."

**Must be visible:** the agent's `active` status, the Authorized Tools list, and the connector page showing
`mcp_kirro_all_v24` healthy with 18 tools plus `whatsapp_kirro`.

> **B:** "Back to you — let's watch someone actually use it."

______________________________________________________________________

## Scene 3 — It's a phone product (A, `PHONE`, 0:35)

**Screen:** the handset. Open `kirro.upayan.dev` in the mobile browser.

**Actions:** browser menu → **Add to Home screen** → open it from the home screen so it launches **standalone**,
with no browser chrome.

> **A:** "Nobody chases a concert ticket on a laptop. KIRRO installs to the home screen and runs as an app — same
> server-rendered pages, same agent, no app store. This is the real thing on a real phone, not a resized window."

**Must be visible:** the KIRRO icon on the home screen, and the app opening **without** a browser address bar.

**Rehearse this.** If the install prompt misbehaves on the day, open the site in the mobile browser and say "on the
phone" instead of "installed" — do not claim the install if it didn't happen.

______________________________________________________________________

## Scene 4 — The declaration, by voice, on the phone (A + C, `PHONE`, 1:40)

**Screen:** the phone, on `/talk`. Start the call. Let the call-id badge and the Listening state land before anyone
speaks.

> **A:** "Every word, both directions, goes through Gnani — speech-to-text on the way in, text-to-speech on the way
> back. In between is the agent Upayan just showed you."

**C** *(speaking into the phone)*: "I want the concert tonight. Front standing. Four of us, but three would still
work. I'll pay up to four and a half thousand rupees each."

**Expected reply, close to this shape:**

> **KIRRO:** "Stadium Concert on [weekday], [date], any slot, 4 people, minimum 3, up to Rs 4,500 per person, so I
> will reserve Rs 18,000, not charge it. Shall I go ahead? Please say yes or no."

> **A:** "Three things in that sentence are load-bearing. It read the date and weekday straight back from the
> release's own record — it's forbidden from doing its own calendar arithmetic, because it used to get that wrong.
> It said *reserve*, not charge. And it's asking for an explicit yes. Nothing has touched money yet."

**C:** "Yes."

*(The agent reserves and pools. Then the `wa.me` popup fires on the "reserved, not charged" phrase.)*

**Action:** tap the popup, send the opening message — **on the same phone**.

> **A:** "WhatsApp only allows a free-form business message inside a window the user opens. So she opens it. That one
> tap is the only reason the result can reach her later — and that's a real WhatsApp Business number."

**Must be visible:** the live transcript on the phone, the call-id badge, the popup, and the WhatsApp thread.

> **A:** "Upayan — what did it actually do?"

______________________________________________________________________

## Scene 5 — What the agent actually did (B, `PLATFORM`, 0:50)

**Screen:** split, or cut between: the platform's chat/audit view for that thread, and the terminal tailing the mock.

> **B:** "Here's the same turn from the platform's side, and here's every request that reached our connectors.
>
> Watch the order. `create_mandate` first, on its own — eighteen thousand rupees, in paise, one million eight
> hundred thousand. It waits for an authorization id and an ACTIVE status. Only **then** does it enter the pool. The
> prompt forbids running those two in parallel, because an early version did exactly that and attached the wrong
> mandate to the bid.
>
> And one more thing worth saying out loud: we trust this log, not the agent's own sentences. An early version once
> announced it had pooled someone's bid when the log showed the call had never been sent. That's why every tool call
> is logged with the arguments that actually arrived, before we validate them."

**Must be visible:** `mcp.create_mandate` then `mcp.declare_interest` in that order, with their arguments.

______________________________________________________________________

## Scene 6 — The pool, from the organiser's side (A, `DESKTOP`, 0:25)

**Screen:** `/admin`.

> **A:** "Same bid, seen by the organiser. One entry in the draw. No booking, no payment — because nothing has been
> allocated and nothing has been charged. Eighteen thousand rupees are blocked in her account, and that's all that's
> happened so far."

**Must be visible:** **Draw entries** at 1, **Captured** still 0, Releases table showing `Entries = 1`.

______________________________________________________________________

## Scene 7 — The window closes, the draw runs (B, `SPLIT`, 1:10)

**Screen:** `/events/<concert id>` countdown on the left, terminal on the right.

> **A:** "The window's closing. Nobody can improve their position in the last ten seconds, because there's no
> position to improve."

*(Hold on the countdown hitting zero and the page switching to "Window closed — the draw runs within 5 minutes.")*

> **B:** "A scheduled job now notices a release whose window has shut and whose draw hasn't run, and asks the
> allocator agent to settle it. That job decides *when* to ask. It never decides what to do — the agent does.
>
> And I'll be straight about why that job exists. The platform's own scheduled Workflow executes zero steps on every
> run. Seven steps defined, the trigger fires, and not one connector call comes out. We ruled out six causes, and
> the endpoint that would tell us why needs an admin role this tenant can't get. So we wrote a five-minute cron job
> that asks the same agent the same question over the chat API. It's a stand-in, and we file it as a platform bug —
> not as architecture."

*(Let the chain run in the terminal.)*

> **B:** "Draw. Hold. Verify the hold is actually active — *before* charging anything. Capture. Confirm. Then release
> the unused part of the mandate in the same run, because 'losing claims aren't released quickly' is exactly the
> failure this product exists to fix."

**Must be visible:** `allocator.draw` → `create_hold` → `get_hold` → `execute` → `confirm_booking` → `release`, in
order, with the booking reference.

______________________________________________________________________

## Scene 8 — The outcome, on her phone (A, `PHONE`, 0:40)

**Screen:** the handset. WhatsApp first, then `/dashboard` in the installed app.

> **A:** "And it arrives where she actually is."

*(The WhatsApp result message lands on the phone.)*

> **A:** "Sent by the agent, through the real WhatsApp connector, to the number she saved. And in the app: booking
> reference, hold, payment. Charged for three — her own stated minimum — with the rest of the reservation released.
> She never refreshed anything, never raced anyone, and never had money taken before she had a seat."

**Must be visible:** the WhatsApp message, then the `BK-####` row and the payment marked SUCCESS, on the phone.

______________________________________________________________________

## Scene 9 — Different human input: she says no (A + C, `DESKTOP`, 0:50)

**Screen:** `/talk`, a fresh call, same concert release. Desktop is fine here — the point is the words, not the
device.

**C:** "Concert tonight, two of us, up to three thousand each."

*(read-back for 2 people)*

**C:** "Actually make it four of us."

> **A:** "'Actually' is a correction signal. It changes the field immediately and reads back again. A different
> number with **no** correction signal gets a question instead — 'you said two earlier, do you want to change it?' —
> because a misheard number and a changed mind sound identical over a phone line."

*(second read-back, now four people)*

**C:** "No."

*(Cut to the terminal.)*

> **A:** "And here's the part worth pausing on. Search the whole log for this conversation. No `create_mandate`. No
> `declare_interest`. Not one rupee was blocked, because she never said yes. Declining costs the user exactly
> nothing — which is the only reason declaring interest is a reasonable thing to ask a person to do."

**Must be visible:** the cancellation line, and the absence of any money tool in the log for that thread.

______________________________________________________________________

## Scene 10 — Hinglish, a vague price, and a rail that fails (A + B, `SPLIT`, 1:30)

**Screen:** `/talk`, fresh call. Switch to the everyday end of the inventory — the courts.

**C:** "Tennis court Saturday, two of us, budget eight to ten thousand, ideally eight."

> **KIRRO (expected):** "What is the single maximum you will pay per person?"

> **A:** "It stored nothing. Not eight, not ten. On a real phone call in September, an earlier version took exactly
> that sentence, read back ten thousand, accepted 'yes I do need it' as confirmation, and closed the declaration. The
> read-back ran perfectly and confirmed the wrong number. That failure is why this rule exists."

**C:** "Shanivaar ko court chahiye, char log."

*(Expected: the whole reply in Hinglish, and because "court" fits both badminton and tennis, it asks which one **and**
the ceiling in one question, keeping Saturday and four.)*

> **A:** "It mirrored the language, and it refused to guess the sport. The language is decided fresh from the newest
> message every single turn — our first attempt at that fix leaned on the Hindi side, fixed the Hinglish case three
> out of three, and broke the English case into Hindi two out of three. We caught it by re-running the English case
> as a regression check, and we threw the fix away."

**Now arm the failure, on camera:** `/admin` → Demo controls → Target `pinelabs.create_mandate` → Scenario
`insufficient_balance` → Set scenario.

> **A:** "The mock is going to fail the next mandate, and the agent isn't told. Scenario control is out of band — its
> requests carry a business payload and a correlation header, no response ever names a scenario, and the switch isn't
> reachable from the tool surface at all. As far as the agent knows, a payment rail just broke."

*(Finish the declaration and say "yes".)*

> **KIRRO (expected):** the amount could not be reserved; try again, or cancel.

> **B:** "Four-oh-two, insufficient balance. Zero mandates in state. And notice what it did **not** say — it never
> said 'reserved', and it never put her in the draw. An agent that reports a success it can't prove is worse than one
> that fails."

**Disarm immediately after the take:** Target `*`, Scenario `success`.

**Must be visible:** the 402 in the log, `mandates: 0`, and no `declare_interest`.

______________________________________________________________________

## Scene 11 — The same agent, a very different event (A, `DESKTOP`, 0:40)

**Screen:** `/` listings, then the Delhivery calls in the terminal.

> **A:** "None of this is specific to concerts. The same mechanism runs a society badminton court at two fifty a
> head, a club tennis slot, an opening-night screening — and an F1 paddock pass, where the thing you win is physical
> and has to be shipped.
>
> Delhivery, at the documented endpoint names: pincode serviceability, order creation, package tracking. And it
> behaves like the real thing when the request is bad — an unserviceable pincode comes back as an empty list with a
> two hundred, not an error, and a repeated order id comes back as a duplicate. Those response bodies are our mock's
> shapes: the paths and the serviceability fields come from Delhivery's own documentation, the rest we couldn't
> verify without a merchant account, and we're not going to claim otherwise."

**Must be visible:** the three Delhivery paths and the empty `delivery_codes` list.

______________________________________________________________________

## Scene 12 — Evidence, and what is honestly broken (B, `PLATFORM`, 1:00)

**Screen:** cut between four surfaces, roughly fifteen seconds each.

**12a — the mock's request log.**

> **B:** "Every verdict in this video comes from here, not from what the agent said about itself."

**12b — Grafana.**

> **B:** "Each call gets an id, and that id reconstructs the whole conversation: every turn, its latency, the thread
> it ran on, any pipeline error."

**12c — the AgenticOrg agent page.**

> **B:** "The agent itself — active, with its shadow twin. And the cost: the entire declare side of this product has
> spent eighty-seven cents."

**12d — the honest list.** Stay here.

> **B:** "Three things are broken, and none of them are in a footnote.
>
> The platform's scheduled Workflow executes zero steps. We replaced it with a cron job.
>
> Tool-call arguments arrive null or corrupted, intermittently, per tool — we disproved nine possible causes on our
> side before filing it.
>
> And the one that matters most: a contested draw with three bidders left nobody booked. The draw ran, the slot's
> capacity went to zero, and all three mandates — including the winner's — were released. Each piece is correct on
> its own; the agent's live orchestration of them is not. We found it two days ago, we filed it, and the honest
> position is that the single-bid path is proven and the multi-bid path is not.
>
> We'd rather show you that than a demo that quietly avoided it."

**Close on** the homepage or the booking reference from Scene 8.

> **A:** "Declare. Draw. Book. No racing."

______________________________________________________________________

## Lines to never say

- "The Workflow runs the draw." It does not; a cron job asks the agent.
- "The allocator reliably books the winner." Not for multiple bids — see the open defect.
- "Pine Labs' connector handles the payment." The platform's `pinelabs_plural` is registered but uncredentialed and
  unused; the real Pine Labs call goes from our server to their UAT sandbox, and the mandate hold/release is mocked
  because no such primitive exists anywhere in Plural.
- "Our Delhivery mock matches the API exactly." Paths and serviceability fields match the docs; create and track
  response bodies are ours.
- "It's installed as an app" — unless the install actually happened in Scene 3.
- Anything citing the platform's Observatory screen: it displays a canned invoice-processing demo that mentions
  neither of our agents.

## If something goes wrong mid-take

Keep rolling. The platform's router sometimes answers "No agent was able to answer that query" — roughly one turn in
four, and over voice the caller hears it out loud. Gnani's text-to-speech returns real 500s, which leaves the reply
on screen and silent, with the app saying so. Either is a legitimate thing to narrate in one sentence and move past.
The only takes worth discarding are the ones where **we** said something untrue.

______________________________________________________________________

## Capture this while you record — it is what the written answers are built from

The answers (`submission/round-3-answers.md`) have `<<FILL FROM RUN>>` markers that can only be filled from a real
run. Collect all of this before you tear the setup down:

1. **The run id** you recorded against (`default`, unless you changed it) and the **date**.
1. **The mock's request log for that run** — the single most important artifact:
   `kubectl exec deploy/kirro-mock -n kirro -- cat /app/data/logs/mock/default.jsonl > run.jsonl`. Every timestamp,
   tool, argument and response in the answers comes from this file.
1. **Each call id** from the `/talk` badge (`call_<12hex>`), one per conversation.
1. **The transcript of every conversation** — use the Copy/Download button on `/talk`; it exports as
   `You:` / `KIRRO:` with a timestamped header and the call id.
1. **Which eval case each conversation was** — label them as you go (L01 ambiguous price, L03 Hinglish, L05 the "no",
   L06 insufficient balance, L10 two events). Without the labels the run log is much harder to map to answers.
1. **`GET /__admin/state?run_id=default`** immediately after each take, and once at the end.
1. **The release and booking ids** — `rel_…`, `BK-…`, `auth_…`, `decl_…`.
1. **Screenshots from the platform** (Upayan): the agent detail page, Authorized Tools, the connector list with tool
   counts, and the Audit Log filtered to our agent types.
1. **Anything that went wrong**, including the takes you discarded and why. The answers have a whole section on what
   still fails, and a failure you hit on camera belongs in it.

Hand over the transcripts, `run.jsonl` and the case labels, and the written answers can be completed from them.
