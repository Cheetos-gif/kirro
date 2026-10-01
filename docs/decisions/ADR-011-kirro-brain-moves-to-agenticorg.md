# ADR-011: KIRRO's brain moves to AgenticOrg; this repo becomes connector infrastructure + spec/oracle

Status: accepted (2026-10-02) — **planning only**, not yet implemented. Code changes described here are future
work; this ADR and `docs/agenticorg/*` are the implementation spec for that work.

## Context

The competition requires the judge-facing KIRRO to be the actual AgenticOrg Virtual Employee: AgenticOrg runs and
decides, talking to the world only through registered connectors. The architecture this repo currently has —
`agent/api.py` (FastAPI, port 8080) exposing `agent/core.py`'s `Engine` as the only orchestrator, with AgenticOrg
(if wired at all) calling it over HTTP — is exactly the shape the brief rules out:

```
AgenticOrg --HTTP--> our FastAPI Engine --> decisions      # NOT ALLOWED
```

required instead:

```
Phone/WhatsApp --> AgenticOrg Virtual Employee (decides) --> registered connectors (real + our mocks)
```

ADR-010 already established the connector-level facts (Vachana over Inya, native Pine Labs/Twilio/WhatsApp, 3-slot
mock budget, Delhivery mandatory-and-additional). This ADR covers the orchestration-level consequence: where KIRRO's
decision logic lives, which files change, and the exact AgenticOrg configuration needed. The existing Python Engine
(`agent/core.py`, `agent/state/*`, `agent/policies/*`) is **not deleted**. The brief is explicit that it may remain
as a development/reference implementation, deterministic test oracle, and schema/state specification — it must not
be the thing AgenticOrg delegates decisions to.

______________________________________________________________________

## 1. Current architecture vs. required architecture

|                           | Current (this repo, pre-ADR-011)                                                                         | Required                                                                                                                               |
| ------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Decision-maker            | `agent/core.py` `Engine`, reached via `agent/api.py` or `agent/runner/*`                                 | The AgenticOrg Virtual Employee itself (LLM + platform tool-calling loop)                                                              |
| Where guards/state live   | Python: `agent/state/machine.py` (19 states, transition table, guards)                                   | Natural-language rules in the agent's Prompt/Behavior, backed by connector-side validation where possible                              |
| Where field parsing lives | Python regex: `agent/state/fields.py`, `agent/policies/money.py`                                         | LLM judgment, constrained by verbatim-transcribed rules in the Prompt (see Risk 1)                                                     |
| Voice                     | Gnani Inya `trigger_call` (planned, not built)                                                           | Twilio (native) carries the call; Vachana (custom real connector) does STT/TTS — ADR-010                                               |
| Multi-user pooling        | `Engine(competitors=[...])` constructor arg — no real multi-user state, evals inject competitors by hand | Must persist across separate per-user AgenticOrg conversations; see §4 "Pool" design below                                             |
| Allocation trigger        | `Engine.on_event({"type":"window_open"})`, called directly in-process by evals/local runner              | A scheduled trigger on the live platform (native **Agent Scheduler** connector) firing a Workflow                                      |
| Judge-facing surface      | `agent/api.py` HTTP API + `web/` dashboard reading it                                                    | The AgenticOrg Agent itself (phone/WhatsApp), observed via AgenticOrg's own Audit Log/Observatory, optionally mirrored to `web/` later |

______________________________________________________________________

## 2. Files that need changing (future work, not done in this change)

- `mock_server/app.py`: trim to exactly the 4 AgenticOrg-facing surfaces (venue inventory+hold+**pool**, Pine Labs
  mandate hold/release, DIFD-as-an-endpoint, Delhivery). Remove the `/gnani/extract` HTTP route — Vachana returns
  real transcripts now, so there is no mock to serve there; the deterministic extractor stays in
  `connectors/gnani/extract.py` as reference/oracle code only, unexposed.
- `mock_server/app.py` / `allocator/`: add a new route, e.g. `POST /allocator/draw`, that wraps
  `allocator.engine.allocate()` so AgenticOrg can call DIFD as a tool instead of our Python Engine calling it
  in-process. Pure function, so it goes through the same `serve()` scenario-injection wrapper as the other 3 mocks
  for infrastructure consistency (timeout/malformed/upstream_500 are still meaningful — the *call* to it can fail
  even though the function itself is deterministic).
- `mock_server/app.py` / venue routes: add a **declare-interest / pool** endpoint on the venue-inventory mock (see
  §4 "Pool" below) — this is a sub-capability of budgeted mock #1 (venue inventory + hold), not a new, 4th slot.
- `config/connectors.yaml`: align with ADR-010 — mark `pine_labs` as the native `pinelabs_plural` connector for the
  real leg, add a distinct `pine_labs_mandate` mock entry, drop the `gnani` key in favour of `vachana` (real,
  custom-registered, not ours to mock), note `twilio` as platform-native (nothing to configure in this repo).
- `docs/connectors.md`: add the new `/allocator/draw` and pool-declare routes to the route table once built.
- `agent/api.py`: retire from "the production brain's HTTP surface." It may keep running as a local dev/test
  harness for the oracle Engine (what `evals/harness.py` already uses via `TestClient`), but nothing on the demo
  path points the live AgenticOrg agent at it.
- `AGENTS.md`: update "What KIRRO is" and the architecture map to label `agent/core.py`, `agent/api.py`,
  `agent/runner/*` as reference/oracle, not production (done in this change, see diff).

## 3. Files that stay as-is (repurposed as spec/oracle, not touched)

- `agent/state/machine.py`, `agent/state/fields.py`, `agent/policies/*` — the deterministic specification this ADR
  transcribes into `docs/agenticorg/agent-spec.md`'s Prompt/Behavior text. Kept runnable so `uv run pytest` keeps
  proving the spec is internally consistent even after the platform becomes the real decision-maker.
- `agent/core.py`, `agent/tools/*`, `agent/runner/*`, `agent/system-prompt/*` — kept as the local oracle: evals
  (`evals/cases/E01..E10.yaml` via `evals/harness.py`) keep running against it exactly as today, now explicitly
  documented as testing the spec, not the demo path.
- `allocator/engine.py`, `allocator/fairness.py` — unchanged; becomes the implementation behind the new
  `/allocator/draw` mock route.
- `connectors/inventory/venue.py`, `connectors/pine_labs/mock.py`, `connectors/delhivery/mock.py` — unchanged;
  these already are the mock_server's implementation, just trimmed at the HTTP-exposure layer (§2).
- `connectors/gnani/extract.py` — kept as reference for how to read a transcript deterministically offline; no
  longer called by anything on the demo path (Vachana + the live agent's own reasoning replace it).
- `connectors/gnani/platform.py` (Inya `trigger_call`) — becomes historical/dead code under ADR-010; not deleted
  yet, flagged for removal in the implementation pass since Vachana replaces it entirely.
- `logging_/decision_log.py`, `tests/`, `evals/` — unchanged.

## 4. What moves into AgenticOrg

The brief's 17-item ownership list, mapped to where each one lives on the platform. Two platform objects are
needed, not one — see the reasoning below the table.

| #   | Item                        | AgenticOrg mechanism                                                                                                                                                                                             |
| --- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Declaration                 | Declare Agent's Prompt collection loop (event, date, group size, ceiling, optional time window)                                                                                                                  |
| 2   | Constraint validation       | Declare Agent's Behavior rules, transcribed verbatim from `fields.py`/`money.py` (Risk 1)                                                                                                                        |
| 3   | Read-back                   | Declare Agent Prompt rule: present the summary, do not advance without an explicit yes                                                                                                                           |
| 4   | Correction handling         | Declare Agent Behavior rule: only an explicit correction word changes an already-set field                                                                                                                       |
| 5   | Verification                | Declare Agent calls the Pine Labs-mandate mock's hold/authorize op after read-back confirms                                                                                                                      |
| 6   | Mandate authorisation flow  | Declare Agent tool call to the budgeted Pine Labs-mandate mock                                                                                                                                                   |
| 7   | Waiting until release       | Declare Agent writes the bid into the venue-inventory mock's pool (§ below) and ends the call                                                                                                                    |
| 8   | Pool participation          | Venue-inventory mock's pool store (sub-capability of budgeted mock #1)                                                                                                                                           |
| 9   | DIFD allocation invocation  | Window-Allocation **Workflow**, triggered by the native Agent Scheduler connector                                                                                                                                |
| 10  | Winner/loser handling       | Window-Allocation Workflow, branching on `/allocator/draw`'s per-bid status                                                                                                                                      |
| 11  | Capture                     | Workflow calls Pine Labs-mandate mock's execute op for winners                                                                                                                                                   |
| 12  | Release                     | Workflow calls Pine Labs-mandate mock's release op for losers/expired                                                                                                                                            |
| 13  | Group atomicity logic       | Already inside DIFD (capacity checked at assignment time, ADR-002); Workflow just reads the result                                                                                                               |
| 14  | Re-declaration after losing | Loss/expiry notification (WhatsApp, native) invites a fresh Declare Agent conversation                                                                                                                           |
| 15  | Exception handling          | Both the Declare Agent and the Workflow refuse/report per the transcribed guard rules (Risk 1)                                                                                                                   |
| 16  | User notifications          | Workflow sends outcome via native WhatsApp (`whatsapp_kirro`, already connected)                                                                                                                                 |
| 17  | Group fallback decision     | Declare Agent asks the user's minimum-acceptable group size at declare time, mirrors it in the read-back (existing `min_group_size` field, currently under-surfaced in v0 — see `docs/agenticorg/agent-spec.md`) |

**Two platform objects, not one.** AgenticOrg Agents are per-conversation; there is no built-in way for one
in-progress phone call to know about every other user's declaration for the same release. KIRRO needs:

1. **"Kirro Declare" Agent** — the conversational Virtual Employee a judge talks to (phone via Twilio+Vachana, or
   WhatsApp). Owns items 1–8, 14, 17. Ends each conversation once the user is "in the pool" or has cancelled.
1. **"Kirro Window Allocation" Workflow** — a scheduled, non-conversational job, triggered when a release's
   `opens_at` is reached. Owns items 9–13, 15 (post-pool), 16. Triggering mechanism: the native **Agent Scheduler**
   connector (`schedule_agent_task`, confirmed in the catalog, ADR-010) — the Declare Agent calls
   `schedule_agent_task` once it knows a release's `opens_at`, targeting the Workflow.

This two-object split is a design decision made in this ADR, not something verified against a named AgenticOrg
feature called "multi-agent pooling" — flagged in Risks §7.

## 5. What stays as external connector/mock infrastructure

Unchanged from ADR-010, restated for completeness:

- **Real, native**: Twilio (call transport), WhatsApp (`whatsapp_kirro`, notifications + text declare channel),
  Pine Labs (`pinelabs_plural`: order/payment-link/refund), Gmail (only if an external-input routing need appears).
- **Real, custom-registered**: Vachana (STT/TTS, `api.vachana.ai`).
- **Mocked, budgeted (3 slots)**: venue inventory + time-boxed hold + pool, Pine Labs mandate hold/release,
  DIFD allocator (as an endpoint).
- **Mocked, mandatory and additional**: Delhivery (serviceability/create/track, documented shapes).

## 6. Exact AgenticOrg configuration needed

Full copy-pasteable artifacts are in `docs/agenticorg/`:

- `docs/agenticorg/agent-spec.md` — Kirro Declare Agent: Persona, Role, Prompt (verbatim), Behavior rules,
  Authorized Tools list, tool invocation contracts, failure-handling rules, memory/state requirements.
- `docs/agenticorg/workflow-spec.md` — Kirro Window Allocation Workflow: trigger, steps, idempotency, notification
  templates.
- `docs/agenticorg/setup-runbook.md` — connector registration field-by-field, env/secrets needed, demo steps.
- `docs/agenticorg/evals.md` — eval cases written against the live agent (not the local oracle).

## 7. Risks and gaps

1. **Field-parsing determinism loss.** `fields.py`/`money.py` are regex: deterministic, unit-tested, unambiguous
   about "8 to 10k, ideally 8" or "any day." On AgenticOrg, the mock-capability budget is fixed at exactly 3
   (venue, Pine Labs mandate, DIFD) with no slot left for a "field parser" tool, so this logic becomes LLM
   judgment constrained by prose rules transcribed as literally as possible into the Prompt (`agent-spec.md`).
   This is a real behavioural downgrade, not a wash — flagging it rather than asserting equivalence. Mitigation:
   the Prompt quotes the exact ambiguity trigger words and the exact "same weekday means +7 days, never today"
   rule, etc., instead of paraphrasing; eval cases E02–E04's inputs are kept as the regression set.
1. **Non-MCP custom connector tool-shape is unverified.** `Register Connector`'s form has an MCP checkbox whose
   tooltip explains auto tool-catalog discovery; registering **without** it (plain REST, which is what Vachana
   needs — see ADR-010) showed no visible field for declaring individual operations beyond Base URL + Auth +
   "Extra config (JSON)". How AgenticOrg exposes a non-MCP custom connector's operations to an agent was not
   observed live (browser session was lost before the Role/Prompt/Behavior wizard steps could be inspected).
   Two fallbacks if a plain custom connector doesn't give per-operation tools: (a) put a tiny MCP shim in front of
   Vachana ourselves and register *that* with the MCP checkbox on, same as Delhivery; (b) use the "Extra config
   (JSON)" field if it turns out to accept an operation list. Needs live verification before registering Vachana.
1. **Pool persistence is a design choice, not a verified platform feature.** AgenticOrg has no cross-conversation
   memory primitive we observed. §4's "venue-inventory mock also stores the declared-interest pool" is this ADR's
   proposed answer, chosen because it reuses budgeted mock #1 instead of asking for a 4th slot — but it is a scope
   extension of "time-boxed hold" beyond its literal wording. Flagging for explicit confirmation before building.
1. **Two platform objects (Agent + Workflow) are a design decision**, not a verified "this is how AgenticOrg wants
   multi-user fairness done" pattern. `Workflows` and `client.workflows.generate/create/run` were confirmed to
   exist (A2A/MCP integrations page); whether a Workflow can itself message a user over WhatsApp/Twilio, or
   whether that has to be delegated back to an Agent step inside the Workflow, needs live verification.
1. **Static per-agent tool ACL** (ADR-010) means AgenticOrg cannot stop the Declare Agent from calling, say, the
   Pine Labs-mandate execute op before a hold exists — the Behavior rules in `agent-spec.md` are necessary but not
   platform-enforced; the connector-side mocks should reject invalid sequences too (e.g. `execute` on a mandate
   that was never `create`d), which the current mock already partially does (404 NOT_FOUND) and should keep doing.
1. **Governance duplication.** `logging_/decision_log.py`'s DecisionRecord may duplicate AgenticOrg's own Audit
   Log/Observatory for a platform-hosted agent (ADR-010 open question, still open). Q1.2 reconstruction
   (`scripts/reconstruct.sh`) currently reads our JSONL; if the production agent's real decisions live only in
   AgenticOrg's audit trail, reconstruction needs a second path pulling from there. Not resolved by this ADR.

## 8. Implementation plan, in dependency order

1. Verify the two unresolved platform facts (Risks 2 and 4) live: inspect the Role/Prompt/Behavior/Review wizard
   steps fully, register one throwaway non-MCP custom connector to see what tool shape it produces, check whether
   `Workflows` can call native connectors (WhatsApp/Twilio) directly.
1. Build the mock-server changes (§2): trim to 4 surfaces, add `/allocator/draw`, add the pool-declare endpoint on
   venue inventory, update `connectors/mock_schemas.py` for any new response shapes, update
   `tests/test_mock_server.py` and `docs/connectors.md`.
1. Update `config/connectors.yaml` per ADR-010/§2.
1. Register the real connectors on AgenticOrg: Vachana (needs a `speechstack@gnani.ai` API key first — external
   prerequisite), confirm Twilio/`pinelabs_plural`/WhatsApp are reachable from this tenant with real credentials.
1. Register the 4 mocks as custom/MCP connectors once (2) is deployed somewhere AgenticOrg can reach (public URL —
   Vercel or equivalent; local `mock_server/` is not reachable from the hosted platform).
1. Build "Kirro Declare" Agent from `docs/agenticorg/agent-spec.md`, restricting Authorized Tools to exactly the
   list given there.
1. Build "Kirro Window Allocation" Workflow from `docs/agenticorg/workflow-spec.md`; wire the Agent Scheduler
   trigger.
1. Run `docs/agenticorg/evals.md`'s cases against the live agent; keep `evals/cases/E01..E10.yaml` running against
   the local oracle in parallel as the regression baseline for the Prompt-transcribed rules.
1. Demo runbook (`docs/agenticorg/setup-runbook.md`) dry run end to end.
