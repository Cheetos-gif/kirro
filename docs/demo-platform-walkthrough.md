# The Pine Labs platform, click by click

What to open, what to click, and what to say, for every shot that happens on
`https://agenticorg.hackathon.pinelabs.com`. Written so someone who has never used the platform can present it.

Companion to `demo-script.md` (the scenes) and `demo-cue-card.html` (the cue cards). Everything here was verified
live on 2026-10-04 — but the platform is a shared tenant that other teams write to, so **walk it once before you
record** and correct this file if a screen has moved.

## Sign in first

`https://agenticorg.hackathon.pinelabs.com/login` → email + password (the `upayanm3@gmail.com` account). **Not**
"Sign in with SSO" — that is Azure AD and not our account. The product lives under `/dashboard/*`; `/` is a
marketing page.

Do this **before** you start recording, in the browser profile you will record from. A session expiry mid-take
dumps you back on the login form.

## The five URLs you actually need

Paste these straight into the address bar. Do not hunt through the sidebar on camera — it has 19 entries and most
of them are irrelevant.

| Shot            | URL                                              | Why                                                         |
| --------------- | ------------------------------------------------ | ----------------------------------------------------------- |
| The agent       | `/dashboard/agents` → click **Kirro Declare v6** | shows it is a real Virtual Employee, active, with its tools |
| Its tools       | the agent's **config** tab                       | the six-tool least-privilege list                           |
| Its prompt      | the agent's **prompt** tab                       | the live system prompt                                      |
| Its cost        | the agent's **cost** tab                         | under a dollar for the whole product                        |
| The connectors  | `/dashboard/connectors`                          | real WhatsApp + Gnani + our MCP mock surfaces               |
| The audit trail | `/dashboard/audit`                               | the platform's own immutable event log                      |

______________________________________________________________________

## Shot 1 — The agent fleet (`/dashboard/agents`)

**What you see:** a list of agents. Four are ours — `Kirro Declare v6` (active), `Kirro Declare v6-dev` (shadow),
`Kirro Declare v4` (retired, with a red "Below Floor" badge), `Kirro Allocator` (active). The other five
(Vendor Manager, Support Triage, Compliance Guard, It Operations, Contract Intelligence) are the platform's seed
agents and are not ours — say so if they are in frame.

**Say:**

> "These are our agents, running on Pine Labs' platform. Kirro Declare takes the conversation. Kirro Allocator runs
> the draw afterwards. The one marked shadow is a twin with an identical prompt — every prompt change goes there
> first, so a bad change never reaches a real caller. The retired one is the previous version; we kept it instead
> of deleting it, because its three hundred and ten samples are our evidence."

**Watch out:** the stat cards at the top animate from zero when the page loads. A screenshot taken mid-animation
shows the wrong numbers. Let the page settle for a few seconds before you narrate a figure.

______________________________________________________________________

## Shot 2 — Inside the agent (click **Kirro Declare v6**)

You land on a tab strip: **overview · workspace · config · Workflow Config · prompt · shadow · cost · scopes ·
learning · voice**. You only need four of them, in this order.

### 2a. `overview`

Shows the agent's status, its model, and its most recent run. There is a collapsed **"▸ Why did the agent do
this?"** panel on the latest run — expand it. It lists the steps the agent took, a confidence percentage for that
run, and feedback buttons.

**Say:**

> "The platform keeps its own explanation of each run — the steps it took and how confident it was."

**Do not click** 👍, 👎 or **Correct this**. They write feedback into the agent's learning pipeline.

### 2b. `config` — the important one

Scroll to **Authorized Tools**. Six entries: `get_release`, `create_mandate`, `get_mandate_balance`,
`declare_interest`, `cancel_declaration`, `release`.

**Say:**

> "Six tools. It can look up a release, reserve money, check that reservation, enter the pool, cancel that entry,
> and release the money. Look at what's missing: it cannot charge anyone, it cannot create a booking, and it cannot
> run the draw. A second agent does those, after the conversation is over.
>
> That split matters because the platform's tool permissions are static — there's no 'allow this tool only in that
> state'. So the only way to enforce least privilege is to not grant the tool at all. The ordering inside the
> conversation is enforced by the prompt; the hard boundary is enforced here."

Also visible on this tab: LLM model, Max Retries, Retry Backoff, HITL Condition, Confidence Floor. There is an
**Edit** button — **do not click it**.

### 2c. `prompt`

The live system prompt, in full. Scroll it slowly; do not read it out.

**Say:**

> "This is the whole agent. No state machine, no code of ours in the decision path — a prompt, six tools, and the
> platform's own loop. Everything in here that looks oddly specific is a scar: a rule we added because a real call
> went wrong. The paise multiplication example is there because it once reserved twelve rupees instead of twelve
> hundred. The rule about never computing a weekday is there because it got the weekday wrong."

### 2d. `cost`

Monthly Cap $200.00 · Current Spend ~$0.88 · Tokens Used ~2.3M · Tasks Run 65 · Budget Utilization 0.4%.

**Say:**

> "And the whole declare side of this product has cost under a dollar."

### Tabs to skip, and why — in case someone asks

- **shadow** — sample count and accuracy versus the promotion threshold. Useful but slow to explain.
- **scopes** — a Grantex scopes table where every row reads `not issued`, even though the tool calls demonstrably
  work. **Do not show this as evidence of anything.** It is a platform tracking gap, not a statement about our
  agent.
- **Workflow Config** — empty on both our agents, which confirms they run the platform's default loop and not a
  custom graph. Nothing to see.
- **workspace**, **learning**, **voice** — unused by us.

______________________________________________________________________

## Shot 3 — The connectors (`/dashboard/connectors`)

**Wait for this page to load before you talk.** It renders 101 catalog cards and is the slowest page on the site;
give it five to eight seconds.

Stay in the **Connected Connectors** region at the top. The ones that matter:

| Connector           | Say this about it                                                                                                                                                                                    |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `whatsapp_kirro`    | **real** WhatsApp Business connector — this is what messages the user their result                                                                                                                   |
| `mcp_vachana_kirro` | **real** Gnani credential. Its health badge says `not_configured`, and that is a platform quirk, not a broken key — the checker insists on discovering MCP tools even for a connector that isn't MCP |
| `mcp_kirro_all_v24` | our four mocked surfaces as one MCP connector, **18 tools**, healthy                                                                                                                                 |
| `pinelabs_plural`   | registered on this tenant but **uncredentialed and unused** — be straight about it                                                                                                                   |

**Say:**

> "The agent only reaches the world through connectors. WhatsApp is the real one. Speech is Gnani — real key, and
> that health warning is the platform insisting on checking it as if it were an MCP server, which it isn't.
>
> Our four mocked surfaces come in as a single connector with eighteen tools. It's one connector and not four for a
> reason we found the hard way: the platform scopes at most one untrusted custom connector per agent, so with two
> registered, one silently wins and the other's tools get rejected.
>
> And this one — the platform's own Pine Labs connector — is registered but has no credentials on this tenant, so
> we don't use it. Our real Pine Labs call goes from our own server to their UAT sandbox instead."

**Do not click, on any connector:** `Archive` (it is behind a browser confirm dialog and we have lost a live
connector to a stray click before), `Health Check` (writes state), `Register Connector`, or `Save` inside any
edit form. Clicking a connector's **Edit** just navigates to a read-only info page — that one is safe, and it
shows the full 18-tool list if you want it in frame.

______________________________________________________________________

## Shot 4 — The audit trail (`/dashboard/audit`)

The platform's immutable event log. Use the **"Filter by event type"** box.

**Say, and do not skip the caveat:**

> "The platform keeps its own audit trail of everything the agents did. One honest note: this tenant is shared
> across competition teams, so this log has other teams' agents in it too — you'll see unrelated rows if you page
> through. We filter on our own agents. For the detail of what actually reached our connectors, the mock's own
> request log is the better source, because it records the arguments that arrived."

**Do not click** `Export Evidence Package` or `Download CSV` on camera — untested, and it triggers a file save in
your real browser.

______________________________________________________________________

## Shot 5 — the Workflow, if you show it at all (`/dashboard/workflows`)

Optional, and only if you are telling the "what's broken" story properly.

Open `Kirro Window Allocation`. Seven steps, trigger `schedule`, active.

**Say:**

> "This is the platform's own scheduled workflow, and it's the honest failure of this project. Seven steps defined,
> the trigger fires on time, and it executes zero of them — no connector call, no audit event, every single run. We
> ruled out six causes. The endpoint that would tell us why needs an admin role this tenant can't be granted. So we
> wrote a five-minute cron job that asks the same agent the same question over the chat API instead. It's a
> stand-in, and we file it as a platform bug, not as our architecture."

**Never click `▶ Run Pipeline` on camera.** It fires a real draw against live state.

______________________________________________________________________

## The do-not-touch list, in one place

On a shared tenant, in a real session, while recording:

| Never click                    | Where                  | Why                                                                  |
| ------------------------------ | ---------------------- | -------------------------------------------------------------------- |
| `Archive`                      | connectors list        | native confirm dialog; has silently archived a live connector before |
| `Health Check`                 | connectors             | writes state                                                         |
| `Register Connector`, `Save`   | connector forms        | creates or mutates tenant-wide config                                |
| `▶ Run Pipeline`               | workflow detail        | fires a real draw → hold → charge chain                              |
| `Approve` / `Reject` / `Defer` | `/dashboard/approvals` | a real decision on a live conversation                               |
| `Run`                          | `/dashboard/rpa`       | fires real automation against government portals                     |
| 👍 / 👎 / `Correct this`       | agent overview         | writes into the learning pipeline                                    |
| `Edit` → `Save`                | agent config           | changes the live agent                                               |
| `Export Evidence Package`      | audit log              | untested file save                                                   |

______________________________________________________________________

## Two screens you should not show as evidence

- **`/dashboard/observatory`** — looks impressive and is entirely canned. It renders a fixed "Invoice Processing
  Pipeline" demo with a fake live feed and names neither of our agents. Showing it as our run would be a false
  claim.
- **`/dashboard/scopes`** and the agent's **scopes** tab — all zeros and `not issued`, despite tool calls
  demonstrably working. Platform tracking gap. Do not present it either as proof or as a failure of ours.

______________________________________________________________________

## If the platform misbehaves on camera

| Symptom                                               | What it is                                                                                                    | What to do                                                                          |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| "No agent was able to answer that query"              | the platform's router refusing its own agent; roughly one turn in four, both agents, not caused by our prompt | say exactly that in one sentence and retry. Over voice the caller hears it out loud |
| A tool call comes back with null or garbled arguments | a known platform defect, intermittent and per-tool; `create_mandate` always lands, the others come and go     | narrate it as the filed bug it is, or retake                                        |
| Stat cards show zeros                                 | they animate up from zero on load                                                                             | wait, then narrate                                                                  |
| Dumped to `/login`                                    | session expired                                                                                               | sign back in; this is why you sign in before recording                              |
| A connector page hangs                                | 101 catalog cards                                                                                             | wait five to eight seconds; don't refresh mid-sentence                              |
