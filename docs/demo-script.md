# Demo video — final script

This is the shooting script: every scene, the page on screen, the words spoken, and the frame that proves it.
`docs/demo.md` is the operational plan behind it (pre-flight, hazards, what must never be filmed). The written
answers are a **separate submission** and are not read out here — this video has to stand on its own.

**Runtime target: 7:30–8:30.** Two voices: **N** = narrator (voice-over, you), **C** = the caller (a teammate, playing
the user, speaking into the browser microphone). Nothing in this script has the narrator explaining what the agent
is about to decide — the agent decides, then we show the log.

| #   | Scene                                                           | Screen                        | Runtime |
| --- | --------------------------------------------------------------- | ----------------------------- | ------- |
| 0   | Cold open — the problem                                         | `/` homepage                  | 0:35    |
| 1   | An organiser puts a concert up for a draw                       | `/organiser`                  | 0:45    |
| 2   | The declaration, by voice                                       | `/talk`                       | 2:00    |
| 3   | The pool, from the other side                                   | `/admin`                      | 0:30    |
| 4   | The window closes, the draw runs                                | `/events/<id>` + terminal     | 1:10    |
| 5   | The outcome                                                     | `/dashboard` + a real handset | 0:40    |
| 6   | Different input: she says no                                    | `/talk` + terminal            | 0:50    |
| 7   | Different input: Hinglish, a vague price, and a rail that fails | `/talk` + `/admin`            | 1:30    |
| 8   | The same agent, a very different event                          | `/talk`, F1 + Delhivery       | 0:40    |
| 9   | Evidence, and what is honestly broken                           | AgenticOrg, Grafana, logs     | 1:00    |

______________________________________________________________________

## Scene 0 — Cold open (0:35)

**Screen:** `https://kirro.upayan.dev`, top of the page. Scroll slowly through the hero, the allocation diagram and
the draw visualiser. Do not click anything.

> **N:** "A stadium concert puts ten front-standing places on sale. Four thousand people want them. Today, those ten
> go to whoever's browser renders the Buy button first — which means they go to bots, to the fastest connection, to
> luck dressed up as fairness.
>
> KIRRO does something else. You *declare* what you want and what you'll pay. Your money is blocked, not spent. When
> the window closes, one seeded draw decides, once. Speed buys you nothing, because there is nothing to race for.
>
> The agent you're about to watch runs as a Virtual Employee on Pine Labs' AgenticOrg platform. It makes every
> decision itself. It reaches the world only through connectors."

**Must be visible:** the hero line "Booking scarce slots shouldn't reward whoever clicks fastest", the draw
visualiser animating, and the live inventory cards further down — which are pulled from the mock, not hard-coded.

**Cut on:** the inventory list.

______________________________________________________________________

## Scene 1 — An organiser puts a concert up for a draw (0:45)

**Screen:** `/organiser`, signed in as an approved organiser.

> **N:** "This is the organiser's side. I'm creating the concert now, live — nothing seeded, nothing pre-baked."

**Actions, on camera, in this order:**

1. **New event** → Event name: `Stadium Concert (Front Standing)` → Status: `published` → Create.
1. **New release** → Event: the concert → How it sells: **Draw** → Date: today → Opens: six minutes from now →
   Slot label: `Front Standing, 20:00` → Starts: tonight 20:00 → Seats: `10` → Price: `4500`.

> **N:** "Ten places. A declare window that closes in six minutes, and a draw that runs the moment it does. Note the
> organiser never chooses a winner — they choose a *rule*."

**Must be visible:** the new release row rendering as **Draw · 0 in the draw**, and the mode badge. If you also show
`/events/<id>`, the page offers only the declare form — the portal cannot sell a draw release, and the server refuses
it with a 409 even if you try.

**Cut on:** the release row appearing.

______________________________________________________________________

## Scene 2 — The declaration, by voice (2:00)

**Screen:** `/talk`. Start the call. Let the call-id badge and the Listening state land before anyone speaks.

> **N:** "Every word in both directions goes through Gnani. Speech-to-text is Gnani Prisma, the reply is Gnani
> Timbre. In between sits the agent on AgenticOrg. Nothing here is a scripted chatbot — it's a tool-calling agent
> with six tools and a system prompt."

**C:** "I want the concert tonight. Front standing. Four of us, but three would still work. I'll pay up to four and a
half thousand rupees each."

*(Expected: the agent looks the release up in that same turn, before it replies — the prompt requires the lookup the
moment one unambiguous event is named — and comes back with the read-back.)*

**Expected reply, close to this shape:**

> **KIRRO:** "Stadium Concert on [weekday], [date], any slot, 4 people, minimum 3, up to Rs 4,500 per person, so I
> will reserve Rs 18,000, not charge it. Shall I go ahead? Please say yes or no."

> **N:** "Three things in that sentence are load-bearing. It read the date and weekday back from the release's own
> record — the prompt forbids it from doing its own calendar arithmetic, because it used to get that wrong. It said
> *reserve*, not *charge*. And it asked for an explicit yes. Nothing has touched money yet."

**C:** "Yes."

**Cut to the terminal** (`kubectl logs -f deploy/kirro-mock -n kirro`) while the agent works:

> **N:** "Watch the order. `create_mandate` first, on its own — eighteen thousand rupees, expressed in paise, one
> million eight hundred thousand. It waits for an authorization id and an ACTIVE status. Only *then* does it enter
> the pool. The prompt forbids running those two in parallel, because an early version did, and attached the wrong
> mandate to the bid."

**Expected closing message:** money reserved and not charged; she is in the draw; the window opens at the time the
release itself reports, read back verbatim; the result arrives on WhatsApp.

**Then:** the `wa.me` popup fires on the "reserved, not charged" phrase. Tap it, send the opening message.

> **N:** "WhatsApp's Business API only allows a freeform message inside a window the user opens. So she opens it. That
> message is the only reason the result can reach her later — and it's a real WhatsApp Business number, not a mock."

**Must be visible:** the live transcript, the call id, `mcp.create_mandate` then `mcp.declare_interest` in the log in
that order, and the WhatsApp thread on the handset.

**Cut on:** the handset showing the sent message.

______________________________________________________________________

## Scene 3 — The pool, from the other side (0:30)

**Screen:** `/admin`.

> **N:** "Same bid, seen by the organiser. One entry in the draw. No booking, no payment — because nothing has been
> allocated and nothing has been charged. Eighteen thousand rupees are blocked in her account and that is all that has
> happened."

**Must be visible:** the **Draw entries** tile at 1, **Captured** still 0, and the Releases table showing
`Entries = 1` against the concert.

**Cut on:** the stat tiles.

______________________________________________________________________

## Scene 4 — The window closes, the draw runs (1:10)

**Screen:** `/events/<concert id>` with the countdown, then the terminal.

> **N:** "The window is closing. Nobody can improve their position in the last ten seconds, because there is no
> position to improve."

*(Hold on the countdown hitting zero and the page switching to "Window closed — the draw runs within 5 minutes.")*

> **N:** "A scheduled job now notices a release whose window has shut and whose draw hasn't run, and asks the
> allocator agent to settle it. That job decides *when* to ask. It never decides what to do — the agent does that.
>
> And I'll be honest about why that job exists at all: the platform's own scheduled Workflow executes zero steps on
> every run. Seven steps defined, the trigger fires, and not a single connector call comes out. We ruled out six
> causes, and the endpoint that would tell us why is behind an admin role this tenant cannot obtain. So we wrote a
> five-minute cron job that asks the same agent the same question over the chat API. It's a stand-in, and we file it
> as a platform bug, not as architecture."

**Cut to the terminal and let the chain run:**

> **N:** "Draw. Hold. Verify the hold is actually active — *before* charging anything. Capture. Confirm. Then release
> the unused part of the mandate in the same run, because 'losing claims aren't released quickly' is exactly the
> failure this product exists to fix."

**Must be visible:** `allocator.draw` → `create_hold` → `get_hold` → `execute` → `confirm_booking` → `release`, in
order, with the booking reference in the confirm response.

**Cut on:** `CONFIRMED`.

______________________________________________________________________

## Scene 5 — The outcome (0:40)

**Screen:** `/dashboard`, then the handset.

> **N:** "Booking reference, hold, payment. Captured for three — the group's own stated minimum — and the rest of the
> reservation released. She never refreshed anything, never raced anyone, and never had money taken before she had a
> seat."

*(Handset: the WhatsApp result message arrives.)*

> **N:** "Sent by the agent, through the real WhatsApp connector, to the number she saved."

**Must be visible:** the `BK-####` row, the payment marked SUCCESS, and the WhatsApp message on a real phone.

**Cut on:** the phone.

______________________________________________________________________

## Scene 6 — Different human input: she says no (0:50)

**Screen:** `/talk`, a fresh call.

> **N:** "Same agent, same event, different human. This time she changes her mind twice."

**C:** "Concert tonight, two of us, up to three thousand each."

*(Read-back.)*

**C:** "Actually make it four of us."

> **N:** "'Actually' is a correction signal in the prompt. It changes the field immediately and reads back again. A
> *different number with no correction signal* gets a question instead — 'you said two earlier, do you want to change
> it?' — because a misheard number and a changed mind sound identical over a phone line."

*(Second read-back, now four people.)*

**C:** "No."

**Cut to the terminal.**

> **N:** "And here's the part worth pausing on. Search the whole log for this conversation. No `create_mandate`. No
> `declare_interest`. Not one rupee was blocked, because she never said yes. Declining costs the user exactly
> nothing — which is the only reason declaring interest is a reasonable thing to ask a person to do."

**Must be visible:** the agent's cancellation line, and the absence of any money tool in the log for that thread.

**Cut on:** the empty grep.

______________________________________________________________________

## Scene 7 — Different human input: Hinglish, a vague price, and a rail that fails (1:30)

**Screen:** `/talk`, a fresh call. Switch to the everyday end of the inventory — the society badminton court.

**C:** "Tennis court Saturday, two of us, budget eight to ten thousand, ideally eight."

> **KIRRO (expected):** "What is the single maximum you will pay per person?"

> **N:** "It stored nothing. Not eight, not ten. On a real phone call in September, an earlier version of this agent
> took exactly that sentence, read back ten thousand, accepted 'yes I do need it' as confirmation, and closed the
> declaration. The read-back ran perfectly and confirmed the wrong number. That failure is why this rule exists."

**C:** "Shanivaar ko court chahiye, char log."

*(Expected: the whole reply in Hinglish, and because "court" fits both badminton and tennis, it asks which one **and**
the ceiling in a single question, keeping Saturday and four.)*

> **N:** "It mirrored the language, and it refused to guess the sport. And the language is decided fresh from the
> newest message every single turn — our first attempt at this fix leaned on the Hindi side, fixed the Hinglish case
> three times out of three, and broke the English case into Hindi two times out of three. We caught that by re-running
> the English case as a regression check, and we threw the fix away."

**Now arm the failure, on camera.** Switch to `/admin` → Demo controls → Target `pinelabs.create_mandate` → Scenario
`insufficient_balance` → Set scenario.

> **N:** "The mock is going to fail the next mandate. The agent isn't told. Scenario control is out of band — the
> agent's requests carry a business payload and a correlation header, no response ever names a scenario, and the
> switch isn't reachable from the tool surface at all. As far as the agent is concerned, a payment rail just broke."

*(Back on `/talk`, finish the declaration and say "yes".)*

> **KIRRO (expected):** the amount could not be reserved; try again, or cancel.

> **N:** "Four-oh-two, insufficient balance. Zero mandates in state. And notice what it did *not* say: it never said
> 'reserved', and it never entered her in the draw. An agent that reports a success it can't prove is worse than one
> that fails."

**Disarm immediately after the take:** Target `*`, Scenario `success`.

**Must be visible:** the 402 in the log, `mandates: 0` in admin state, and no `declare_interest`.

**Cut on:** the honest failure line.

______________________________________________________________________

## Scene 8 — The same agent, a very different event (0:40)

**Screen:** `/` listings, then `/talk` briefly, then the Delhivery endpoints in the terminal.

> **N:** "Nothing you've seen is specific to concerts. The same mechanism runs a society badminton court at two fifty
> a head, a club tennis slot, an opening-night screening — and an F1 paddock pass, where the thing you win is
> physical and has to be shipped."

*(Show the F1 release. Then the three Delhivery calls.)*

> **N:** "Delhivery, at the documented endpoint names — pincode serviceability, order creation, package tracking. And
> it behaves like the real thing when the request is bad: an unserviceable pincode comes back as an empty list with a
> two hundred, not an error, and a repeated order id comes back as a duplicate. Those response bodies are our mock's
> shapes — the paths and the serviceability fields come from Delhivery's own documentation, the rest we could not
> verify without a merchant account, and we're not going to claim otherwise."

**Must be visible:** `/delhivery/c/api/pin-codes/json/?filter_codes=...`, `/delhivery/api/cmu/create.json`,
`/delhivery/api/v1/packages/json/?waybill=...`, and the empty `delivery_codes` list.

**Cut on:** the duplicate-order response.

______________________________________________________________________

## Scene 9 — Evidence, and what is honestly broken (1:00)

**Screen:** cut between four surfaces, roughly fifteen seconds each.

**9a — the mock's own request log.**

> **N:** "Every verdict in this video comes from here, not from what the agent said about itself. Every request, with
> the arguments that actually arrived, logged before validation — so even a call we reject leaves a trace. We built
> that after an early agent announced it had pooled a bid that the log showed had never been sent."

**9b — Grafana.**

> **N:** "Each call gets an id, and that id reconstructs the whole conversation: every turn, its latency, the thread
> it ran on, and any pipeline error."

**9c — the AgenticOrg agent page.**

> **N:** "The agent itself: active, with a shadow twin we test every prompt change on before it reaches a caller. And
> the cost — the entire declare side of this product has spent eighty-seven cents."

**9d — the honest list.** Stay on this one.

> **N:** "Three things are broken, and none of them are hidden in a footnote.
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

**Close on** the homepage, or the booking reference from Scene 5.

> **N:** "Declare. Draw. Book. No racing."

______________________________________________________________________

## Lines to never say

- "The Workflow runs the draw." It does not; a cron job asks the agent.
- "The allocator reliably books the winner." Not for multiple bids — see the open defect.
- "Pine Labs' connector handles the payment." The platform's `pinelabs_plural` is registered but uncredentialed and
  unused; the real Pine Labs call goes from our server to their UAT sandbox, and the mandate hold/release is mocked
  because no such primitive exists.
- "Our Delhivery mock matches the API exactly." Paths and serviceability fields match the docs; create and track
  response bodies are ours.
- Anything citing the platform's Observatory screen — it displays a canned invoice-processing demo that mentions
  neither of our agents.

## If something goes wrong mid-take

Keep rolling. A platform router failure ("No agent was able to answer that query") hits roughly one turn in four and
the caller hears it out loud; a Gnani text-to-speech outage leaves the reply on screen and silent, with the portal
saying so. Either is a legitimate thing to narrate in one sentence and move past. The only takes worth discarding are
the ones where *we* said something untrue.
