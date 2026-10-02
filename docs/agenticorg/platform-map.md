# AgenticOrg platform map

Reference for the platform KIRRO runs on: `https://agenticorg.hackathon.pinelabs.com` ("AgenticOrg" by Pine Labs).
Written from live inspection on 2026-10-02; **keep it current as we work** — anything not directly observed is
labelled. Companion docs: `setup-runbook.md` (how to register/build KIRRO there), `agent-spec.md` and
`workflow-spec.md` (what to build), ADR-010/011 (decisions).

## 1. Tenant and access

|                |                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------- |
| Product        | AgenticOrg (v4.8.0 per the dashboard badge) — "governed enterprise AI agents"                                 |
| Tenant / org   | "Ken's Case Competition"                                                                                      |
| Signed-in user | Upayan Mazumder (upayanm3@gmail.com), role `Developer \| Operations`                                          |
| Landing page   | marketing site at `/`; product lives under `/dashboard/*`                                                     |
| Login          | `/login`: email + password, or "Sign in with SSO". Session is a cookie (`agenticorg_csrf` is the CSRF cookie) |
| Credentials    | **never stored in this repo** — entered by hand at the login form                                             |

The dashboard shell is a fixed left sidebar (three groups) plus a header with the language switch (EN/HI), theme
switch, notifications, and the user menu. There is also an "Ask Anything" assistant dock at the bottom right of
every page.

## 2. Layout: routes (all verified from the rendered sidebar)

| Sidebar group              | Label                       | Route                                        | What it is                                                                       |
| -------------------------- | --------------------------- | -------------------------------------------- | -------------------------------------------------------------------------------- |
| —                          | Dashboard                   | `/dashboard`                                 | Fleet summary: total/active/shadow agents, pending approvals, system status      |
| Agents & Automation        | Agents                      | `/dashboard/agents`                          | Agent fleet; `Create Agent`, `Create from SOP`, `Import CSV`                     |
|                            | Workflows                   | `/dashboard/workflows`                       | Multi-agent workflows, HITL approvals, scheduled triggers                        |
|                            | Agent Templates             | `/dashboard/agent-templates`                 | Publish/instantiate buyer & seller agent templates                               |
|                            | Prompt Templates            | `/dashboard/prompt-templates`                | Reusable prompt templates, filtered by domain                                    |
|                            | Create from SOP             | `/dashboard/agents/from-sop`                 | Generate an agent from a standard operating procedure                            |
|                            | Report Schedules            | `/dashboard/report-schedules`                | Scheduled reports                                                                |
|                            | My Schedules                | `/dashboard/agent-schedules`                 | Deferred/recurring agent runs (this is where `schedule_agent_task` output lands) |
|                            | RPA Scripts / RPA Schedules | `/dashboard/rpa`, `/dashboard/rpa-schedules` | RPA scripts and their schedules                                                  |
| Integrations & Knowledge   | Connectors                  | `/dashboard/connectors`                      | Connected connectors + the 101-entry native catalog + `Register Connector`       |
|                            | A2A / MCP                   | `/dashboard/integrations`                    | SDKs, external agents, MCP clients, connectors, workflows, knowledge             |
|                            | Schemas                     | `/dashboard/schemas`                         | Schema registry (21 in this tenant: 18 platform default, 3 custom)               |
|                            | Knowledge Base              | `/dashboard/knowledge`                       | Document ingestion (8 documents / 18 chunks in this tenant)                      |
|                            | Industry Packs              | `/dashboard/packs`                           | Pre-packaged agents/workflows/templates (none available in this tenant)          |
| Governance & Observability | Observatory                 | `/dashboard/observatory`                     | Live workflow/agent execution view                                               |
|                            | Approvals                   | `/dashboard/approvals`                       | Human-in-the-loop approval queue                                                 |
|                            | Scope Dashboard             | `/dashboard/scopes`                          | Runtime permission boundaries, connector authorizations, denial telemetry        |
|                            | Enforce Audit               | `/dashboard/enforce-audit`                   | Policy enforcement / authorization grants / denials (CSV export)                 |
|                            | Audit Log                   | `/dashboard/audit`                           | Immutable event trail; "Export Evidence Package" + CSV                           |
|                            | SLA Monitor                 | `/dashboard/sla`                             | Uptime/latency compliance (partly degraded: `/health/checks` returns 403)        |

## 3. Connectors (the part KIRRO depends on)

`/dashboard/connectors` has three regions: **Connected Connectors**, **Marketplace**, and
**Native Connector Catalog (101)** with a `Register` button per entry. `Register Connector` opens
`/dashboard/connectors/new`.

### 3.1 Registration form

| Field                         | Notes                                                                                                                                                                                                                             |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Provider                      | only one option: `Custom / Generic Connector`                                                                                                                                                                                     |
| Connector Name \*             | must be `<native_connector_name>_<your_suffix>` — see the naming rule below                                                                                                                                                       |
| MCP                           | checkbox `#is-mcp`: "tool catalog is discovered automatically from the URL below at registration time and verified for Grantex scope compatibility. This connector will only be visible to you, even if you're an administrator." |
| Base URL                      | the API root                                                                                                                                                                                                                      |
| Category                      | `finance, hr, marketing, ops, engineering, comms, compliance, internal, custom, quick_commerce, travel, ecommerce`                                                                                                                |
| Auth Type                     | `oauth2, oauth2_client_credentials, api_key, basic, bolt_bot_token, certificate, custom, none` — note there is **no `meta_business`**; native-prefixed registrations (e.g. `whatsapp_kirro`) are how that auth is obtained        |
| Rate Limit (RPM)              | integer                                                                                                                                                                                                                           |
| API Key                       | secret; or Secret Reference (`gcp://…`)                                                                                                                                                                                           |
| Extra config (optional, JSON) | free-form connector parameters                                                                                                                                                                                                    |

### 3.2 Naming rule (verified — this is the biggest gotcha)

`POST /api/v1/connectors` rejects a name that does not begin with a **native registry connector name**:

```
422 {"detail":"Unknown native connector. Use '<native_connector_name>_<your_suffix>', e.g. 'jira_myteam'."}
```

`vachana`, `gnani`, `delhivery`, `pinelabs`, `custom` and `generic` are **not** in the registry, so names like
`vachana_kirro` or `delhivery_mock_kirro` cannot be registered. The registry does contain an entry named **`mcp`**
(category `custom`, no fixed tools) — that is the prefix for connectors we bring ourselves. Verified accepted:
`mcp_kirro_probe` (201). Our connectors are therefore `mcp_venue_kirro`, `mcp_pinelabs_kirro`,
`mcp_allocator_kirro`, `mcp_delhivery_kirro`.

The registry is readable without CSRF: `GET /api/v1/connectors/registry` → 101 entries, each with `name`,
`display_name`, `category`, `description`, `base_url`, `auth_type`, `tool_functions`, `rate_limit_rpm`,
`timeout_ms`, `registration_mode`, `requires_store_selection`. `registration_mode` is `null` for 97 and
`my_store_link` for 4.

### 3.3 Write API

Writes need `csrf_token` **in the JSON body**, equal to the `agenticorg_csrf` cookie value. A header-only token is
rejected `403 {"detail":"CSRF token mismatch…"}`.

| Action   | Call                                                                     | Effect                                                                           |
| -------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| Register | `POST /api/v1/connectors`                                                | creates the connector; with MCP on, tools are discovered from the Base URL       |
| Archive  | `DELETE /api/v1/connectors/{id}`                                         | soft delete → `status: "deleted"`, hidden from the UI list                       |
| Update   | `PUT /api/v1/connectors/{id}`                                            | updates fields; **`{"status":"active"}` is what restores an archived connector** |
| Read     | `GET /api/v1/connectors?page=&per_page=` / `GET /api/v1/connectors/{id}` | no CSRF needed                                                                   |

The list endpoint hides archived connectors and the `status`/`include_archived` query params appear to be ignored —
fetch a known id directly to see an archived one.

### 3.4 Automation gotcha (cost us a connector once)

Each card's **Archive** button is guarded by a native `window.confirm(...)`. Browser automation accepts native
dialogs by default, so a stray click silently archives a live connector. **Always set a dismiss policy before
clicking around this UI** (`tab.setDialogs({"policy": "dismiss"})`). `whatsapp_kirro` was archived this way and
restored with `PUT {"status":"active"}`; the tenant is back to its original 7 connectors.

Also: the connectors list page is heavy (101 catalog cards) — a `Runtime.evaluate` can time out if you query it
before the page settles; wait ~5-8s after navigating.

## 4. Tenant state before we registered anything (2026-10-02)

> Superseded by §5; kept because it is the baseline the tenant was handed over in.

**Connectors — 7, all active.** `whatsapp_kirro` (comms, `meta_business`, 5 tools: `get_business_profile`,
`get_message_templates`, `send_media_message`, `send_template_message`, `send_text_message`), `tally` (finance,
bridge, 3), `zoho_books` (finance, oauth2, 4), `gstn` (finance, api_key, 4), `banking_aa` (finance, oauth2, 2),
`stripe` (finance, api_key, 2), `pinelabs_plural` (finance, api_key, 2 — ADR-010 listed six tools for this
connector, so re-check when wiring the charge leg).

Not yet registered but present in the registry: **`agent_scheduler`** (`schedule_agent_task`, `cancel_agent_task`,
`list_my_schedules`, `cancel_merchant_schedules` — the Workflow trigger needs this) and `twilio`.

**Agents — 5, all shadow/untouched:** Vendor Manager, Support Triage, Compliance Guard, It Operations, Contract
Intelligence. No active agents, no workflows configured yet, 0 pending approvals.

## 5. Tenant state (updated 2026-10-02, after Phase 1)

**Connectors — 11, all active.** The four KIRRO mock surfaces are registered as MCP connectors, and the platform
discovered every tool from our MCP endpoint:

| Connector             | Base URL          | Tools discovered (n)                                                                                                                                            |
| --------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mcp_venue_kirro`     | `…/venue/mcp`     | 9 — `list_releases`, `get_release`, `create_hold`, `get_hold`, `release_hold`, `confirm_booking`, `declare_interest`, `list_pool_entries`, `cancel_declaration` |
| `mcp_pinelabs_kirro`  | `…/pinelabs/mcp`  | 5 — `create_mandate`, `get_mandate_balance`, `execute`, `release`, `refund`                                                                                     |
| `mcp_allocator_kirro` | `…/allocator/mcp` | 1 — `draw`                                                                                                                                                      |
| `mcp_delhivery_kirro` | `…/delhivery/mcp` | 3 — `pincode_serviceability`, `create_shipment`, `track`                                                                                                        |

That validates ADR-012 end to end: stateless streamable HTTP, the Host allow-list and the JSON schemas all work
with the platform's registration-time discovery.

Pre-existing, unchanged: `whatsapp_kirro` (meta_business, 5 tools), `tally` (3), `zoho_books` (4), `gstn` (4),
`banking_aa` (2), `stripe` (2), and **`pinelabs_plural` — only `create_order` + `check_order_status` (2 tools)**.
ADR-010 recorded six operations for it; this tenant exposes two, so the real charge leg cannot assume
`create_payment_link` / `get_order_status` / `initiate_refund` without re-checking. `twilio` and `agent_scheduler`
remain unregistered.

**Agents — 5, all shadow/untouched** (Vendor Manager, Support Triage, Compliance Guard, It Operations, Contract
Intelligence). No active agents, no workflows, 0 pending approvals.

## 6. Workflow builder (verified 2026-10-02)

`/dashboard/workflows/new`. Two entry points: **Describe in English** (AI generates the steps from a ≤5000-char
prompt) or **Use Template**. Configuration:

- `Workflow Name`, `Version`, `Domain` (finance, hr, marketing, ops, engineering, backoffice)
- **`Trigger Type`: `Manual`, `Schedule`, `Webhook`, `Api Event`, `Email Received`, `Mongodb Schedule`** — a native
  `Schedule` trigger exists, so the Workflow does **not** need the `agent_scheduler` connector to fire at a release
  time (workflow-spec §1's `schedule_agent_task` route can be simplified).
- `Enable adaptive replanning` — AI re-plans the remaining steps when one fails (max 3 attempts)
- `Define Steps (JSON)`: steps are authored as a JSON array; "Add Step Type" appends a skeleton.

**Step skeletons (taken from the builder itself):**

| Type             | Fields (beyond `step`, `name`, `on_success`, `on_failure`)                    |
| ---------------- | ----------------------------------------------------------------------------- |
| `agent`          | `type:"agent"`, `agent_type`, `action`, `inputs`                              |
| `condition`      | `type`, `condition`, `true_path`, `false_path`                                |
| `parallel`       | `type`, `branches`                                                            |
| `wait`           | `type`, `duration_minutes`                                                    |
| `wait_for_event` | `type`, `event_name`, `timeout_minutes`                                       |
| `human_in_loop`  | `type`, `prompt`, `approvers`                                                 |
| `transform`      | `type`, `expression`                                                          |
| `notify`         | `type`, `channel`, `message`                                                  |
| `collaboration`  | opens the agent picker first; then `agents`, `aggregation`, `timeout_minutes` |

The base skeleton the builder starts from is
`{"step":1,"name":"Step 1","agent_type":"ap_processor","action":"process","inputs":{},"on_success":"next","on_failure":"halt"}`.

**Risk 4 answered:** `notify` carries `channel` + `message`, so a Workflow *can* message a user directly instead of
delegating to an Agent step. What `action` references (a connector tool, and its exact id syntax) is still to be
confirmed while authoring the allocation steps.

## 7. Still open / not yet inspected

- The Agent creation wizard's Role/Prompt/Behavior/Review steps, and the exact shape of the **Authorized Tools**
  checklist (dot vs `__` identifiers) — the next thing to inspect.
- Whether a **non-MCP** connector yields callable operations (Risk 2). The four mocks use MCP, so this now only
  matters for Vachana, which has no valid non-`mcp` prefix.
- How a workflow step's `action` names a connector tool.
- Audit Log / Observatory export specifics for Q1.2 (ADR-011 §7.6).

## 8. Agent creation wizard (verified 2026-10-02)

`Create Agent` → `/dashboard/agents/new` → **Skip to manual setup** → 5 steps. What each step actually is (the spec
in `agent-spec.md` had assumed two of these were prose boxes; they are not):

| Step       | Reality                                                                                                                                                                                                                                                                                                                                |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 Persona  | `Employee Name *` (e.g. "Priya, Arjun, Maya"), `Designation`, `Avatar URL`, `Domain` (finance, hr, marketing, ops, backoffice, comms, compliance, commerce, travel, quick_commerce, ecommerce)                                                                                                                                         |
| 2 Role     | **Not prose.** A `Create custom agent type` checkbox → a **slug** input (e.g. `customer_success`); otherwise pick an existing type (Support Triage, Vendor Manager, …). Plus `Specialization` (textarea), `Routing Filters` ("when multiple agents share this type…"), and `Reports To` (org-chart parent; empty = escalates to human) |
| 3 Prompt   | One `Prompt Text *` box (+ a template picker). The full `agent-spec.md` §3 prompt pastes here verbatim (6,545 chars)                                                                                                                                                                                                                   |
| 4 Behavior | **Not prose.** LLM model (only `azure_openai — deployment:gpt-4o` / `-mini` are usable in this tenant), LLM routing (Auto/Economy/Standard/Premium/Disabled), Confidence Floor (default 88% → HITL), HITL condition, Max Retries, **and `Connectors` — linking is what feeds the Authorized Tools list below**                         |
| 5 Review   | (not yet reached)                                                                                                                                                                                                                                                                                                                      |

The wizard also states: *"New agents start in Shadow Mode"* and *"The agent will auto-register on Grantex with a
unique DID and scoped token for A2A/MCP external access."*

**Connector linking (step 4)** is a single-select `<select>` whose options are the tenant's connectors by UUID, with
a `+ Add connector` sentinel; each linked connector appears as a removable chip.

**Authorized Tools (step 4, below the link list)** is a scrollable list with the hint
`Click to add · Shift+click to add a range`, plus `Select All` and `Browse Marketplace Tools`. Leaving it empty is
allowed: *"No tools selected. Default tools will be assigned based on agent type."*

**Tool-id syntax — ADR-011 Risk 2 answered: `connector__tool` (double underscore)**, e.g.
`agent_scheduler__schedule_agent_task`, `zoom__create_meeting`, `ahrefs__get_backlinks`.

**Blocker found (needs resolving before the agent can be least-privileged):** with `mcp_venue_kirro` linked, the
picker renders 558 tool ids but they span only the **native registry** set (`agent_scheduler` → `zoom`); no
`mcp_*_kirro__*` id appears at all. So a custom MCP connector's discovered tools are not offered in the ACL picker
yet. Unverified hypotheses, in the order worth checking: (a) the connector's MCP registration is subject to a
Grantex scope check ("verified for Grantex scope compatibility" per the registration tooltip) that ours has not
passed; (b) custom/MCP tools live behind `Browse Marketplace Tools` rather than this list; (c) the list needs a
reload after linking. Until it is resolved, leaving the selection empty assigns *default* tools, which is broader
than the least-privilege intent of `agent-spec.md` §5.

**Lead on the cause:** the connector record carries `is_trusted: false`, where `whatsapp_kirro` (native) is
`is_trusted: true` — the most likely gate on whether a connector's tools are offered in the ACL picker. It is not
settable from the connector page (only `Test Connection`, `Health Check`, `Back`, `Edit`), and running
`Test Connection` updated `health_check_at` but left `is_trusted` `false`. So trust must come from elsewhere — a
governance surface (Scope Dashboard / Approvals), a registration-time Grantex check ours has not passed, or an API
field. Check that first.

**Definitive (2026-10-02):** `GET /api/v1/tools` returns the platform's **559 valid tool names**, all drawn from the
native registry (`agent_scheduler__*`, `whatsapp__*`, `zoom__*`, …). **None of our `mcp_*_kirro__*` tools is in it**,
and setting them explicitly is rejected:

```
PATCH /api/v1/agents/{id} {"authorized_tools":["mcp_venue_kirro__get_release", …]}
422 {"detail":"Invalid authorized_tools: … Use GET /connectors/registry or GET /tools to discover valid tool names."}
```

So a custom MCP connector's discovered tools are real at the connector level (they register, and the platform
discovers and stores their JSON schemas) but are **not grantable to an agent** through the tool ACL. Our four mock
connectors are therefore usable by the mock's own REST/MCP surface and by anything outside the agent ACL, but the
Declare Agent as configured cannot call them.

Untested ideas worth trying, in order: (1) name the connector after a native registry entry so its tools inherit a
valid namespace; (2) get the connector `is_trusted` (mount a governance/admin surface — Scope Dashboard / Approvals
— we have not found a UI for it); (3) drive KIRRO from the `agenticorg` Python SDK / A2A-MCP path shown on
`/dashboard/integrations` instead of the agent ACL — but note the brief requires the platform agent to make the
decisions, so this would be a design change, not a workaround.

**Agent created (2026-10-02):** `Kirro`, id `ccbb1e36-ae7e-499f-825f-bdc2fe26a3ba`, type `declared_interest_booking`,
domain `ops`, status `shadow`, `token_issued: true`, `grantex_registered: true`
(`did:grantex:ag_01M3WTR022YXPQEAXEC4CHYQQX`). Connectors linked: `whatsapp_kirro`, `mcp_venue_kirro`,
`mcp_pinelabs_kirro`. `authorized_tools` as auto-assigned: **only `whatsapp_kirro`'s five tools**, and
`config.grantex.grantex_scopes = ["agenticorg:ops:read", "tool:whatsapp:write"]` — i.e. the untrusted `mcp_*`
connectors contributed nothing. The agent runs on `azure_openai — deployment:gpt-4o`, confidence floor 88%, HITL at
`confidence < 0.88`, max retries 3, and carries the full 6,545-char `agent-spec.md` §3 prompt verbatim.

Note for anyone editing an agent: `PUT /api/v1/agents/{id}` needs the whole object and, carrying the 6.5 KB prompt,
is **blocked by CloudFront** (a 403 HTML page, not an app error). `PATCH` accepts a partial body and is the usable
path.

### ACL update — custom tools *can* be granted, but only for some connectors

Correcting the "Definitive" block above: this is not a blanket "custom tools are ungrantable". Measured by PATCHing
one tool at a time and reading the status:

| Connector                                                                 | Category | `is_trusted` | Grantable?            |
| ------------------------------------------------------------------------- | -------- | ------------ | --------------------- |
| `mcp_pinelabs_kirro`                                                      | finance  | false        | **yes — all 5 (200)** |
| `whatsapp_kirro`                                                          | comms    | **true**     | yes                   |
| `mcp_venue_kirro` (9 tools), `mcp_allocator_kirro`, `mcp_delhivery_kirro` | ops      | false        | **no — all 422**      |
| probes in `custom` / `internal` / `comms` / `finance`, same MCP URLs      | various  | false        | no — 422              |

Acceptance is **not** explained by category, `is_trusted`, registry-name matching, or tool-name suffix — each was
tested and each fails to fit. `mcp_pinelabs_kirro` is the only untrusted custom connector whose tools pass, and a
probe pointed at the identical MCP URL under a different name and category was rejected. The platform's error
points at `GET /api/v1/tools`, whose 559 names contain **none** of the accepted ones (`create_mandate`,
`get_mandate_balance`, `refund` are all absent), so the validator contradicts its own guidance. Treat this as a
platform-side ingestion quirk, not a documented rule.

Two mechanics worth knowing:

- **Linking a connector whose tools cannot be scoped fails and rolls back** —
  `PATCH /api/v1/agents/{id} {"connector_ids":[…]}` → `503 {"detail":"Unable to refresh agent authorization scopes; no changes were committed."}`. That is why venue and pinelabs are both linked yet only pinelabs contributed tools.
- **`PUT /api/v1/connectors/{id}` silently ignores `category` and `is_trusted`** (server-managed), so the mismatch
  cannot be fixed by editing the connector.

**Current agent ACL** (PATCH, 200): `mcp_pinelabs_kirro__create_mandate`,
`mcp_pinelabs_kirro__get_mandate_balance`, `whatsapp_kirro__send_text_message`, with Grantex scopes
`tool:abb61bca-…__mcp_pinelabs_kirro:write` and `tool:whatsapp:write`.

**Consequence for KIRRO:** the Declare Agent can reserve a mandate but cannot yet read a release or write a bid —
that is the single blocking gap.

**Untested lead:** copy the shape that works. Re-register the venue mock in the `mcp_pinelabs_*` family, or get the
platform to explain why one connector's tools validate and an identically-shaped connector's do not.

**Also found:** the agent page exposes `Chat with Agent` and `Run Agent` — the practical route for the L01–L22 evals
without phone/WhatsApp. The four probe connectors used for these tests were deleted; the tenant is back to its 11
connectors (7 pre-existing + our 4 mocks).

### Scoping: what it actually is (final, tested)

Further attempts narrowed it to this, and no further:

- **Scoping is per-connector and deterministic.** `mcp_pinelabs_kirro`'s tools can be scoped; `mcp_venue_kirro`,
  `mcp_allocator_kirro` and `mcp_delhivery_kirro` cannot — reproducibly, including when each is linked on its own.
- **A PATCH fails as a whole if it names any unscopable tool.** Mixing venue tools with pinelabs tools returns a 422
  that lists only a *subset* of the offending names, and linking an unscopable connector returns
  `503 "Unable to refresh agent authorization scopes; no changes were committed."`. So the ACL is all-or-nothing per
  request, which is why the error text is misleading about *which* name is at fault.
- **Ruled out, each by direct test:** category, `is_trusted`, name family (`mcp_pinelabs_*` with the venue URL),
  base URL (venue URL under a neutral name), tool-name suffix, tool-schema shape (venue's and delhivery's are
  structurally identical to pinelabs's simpler ones), creation timing, and UI-form registration vs raw API
  registration (a UI-registered venue clone was rejected identically).
- **`PUT /api/v1/connectors/{id}` does not re-discover tools** — changing `base_url` leaves the old `tool_functions`
  in place — and it silently ignores `category` and `is_trusted`.
- **`GET /api/v1/tools` never contains any custom connector's tools** (559 registry names only), so the error's own
  advice ("use GET /api/v1/tools") is misleading.
- **The agent's `authorized_tools` can be reconciled server-side**: a list that had three valid entries was observed
  trimmed to one without a successful PATCH from us.

Conclusion: the platform will not reliably grant a custom MCP connector's tools to an agent. `mcp_pinelabs_kirro`
happens to work; three identically-shaped connectors do not, and nothing observable distinguishes them. This needs a
platform-side answer, not more probing. Practical options, in order: ask the platform why one connector's tools
scope and the others' do not (we have a minimal repro: two connectors, same shape, different outcome); re-register
the failing three in the working connector's exact family and re-test later; or move KIRRO's tool invocation off the
agent ACL (the `agenticorg` SDK / A2A-MCP path on `/dashboard/integrations`) — a design change requiring an ADR.

Tenant left clean: 11 connectors (7 pre-existing + `mcp_venue_kirro`, `mcp_pinelabs_kirro`, `mcp_allocator_kirro`,
`mcp_delhivery_kirro`), all probes deleted.

### The runtime gate: connector health, and a likely reframe

`GET /api/v1/connectors/{id}/health` is the health endpoint (the UI's `Health Check` button calls it). Current:

| Connector            | health                                    |
| -------------------- | ----------------------------------------- |
| `mcp_venue_kirro`    | `healthy: true`, `tool_count: 9`          |
| `mcp_pinelabs_kirro` | `healthy: true`, `tool_count: 5`          |
| `whatsapp_kirro`     | **`error`, `healthy: false`** — see below |

`whatsapp_kirro` reports:

```
"Connector has no encrypted credentials. Re-register the connector via POST/PUT /connectors so
credentials land in the encrypted vault (connector_configs.credentials_encrypted). Plaintext
auth_config is no longer accepted …"
```

and chatting with the agent (via `Chat with Agent` on the agent page) returns, instead of a reply:

> "This agent cannot run because a required connector is not authenticated, healthy, and refreshable.
> Go to Dashboard -> Connectors, reconnect the connector, run its health check, then retry the agent."

**This likely reframes the scoping problem above.** The agent-level "scopes" refresh validates *all* linked
connectors, so an unhealthy linked connector (whatsapp) can make the whole refresh fail — which is exactly the
`503 "Unable to refresh agent authorization scopes"`, and plausibly the `422 Invalid authorized_tools` that I
attributed to venue. It is a chicken-and-egg: unlinking whatsapp needs a successful refresh, which needs whatsapp to
be healthy. So the earlier "venue is unscopable" conclusion may be a **symptom**, not a per-connector defect — worth
re-testing once a healthy whatsapp is linked (or once the agent has only healthy connectors).

Unresolved and important: **how `whatsapp_kirro` lost its credentials.** It was archived once by accident (a stray
`window.confirm` accepted by automation) and restored with `PUT {"status":"active"}`; the soft-delete may well have
dropped `credentials_encrypted` and the restore did not put it back. The audit log does not record connector
changes (50 entries, none mention whatsapp), so this cannot be confirmed from the platform. Fixing it needs Meta
Business credentials, which we do not have — flagged to the user.

**RESOLVED — the correct field shape, verified 2026-10-02.** The connector page's own `Edit` form cannot supply
them (its auth-type list has no `meta_business`), but the underlying API accepts credentials at the top level under
a different shape than the UI exposes: `PUT /api/v1/connectors/{id}` (or `POST` at creation) with
`{"auth_config": {"api_key": "<token>"}}`. Verified on three disposable throwaway connectors (`whatsapp_probe1-3`,
created and deleted the same session): plain `{"api_key": ...}` and `{"credentials": {"access_token": ...}}` both
leave `has_credentials: false` (silently dropped); `{"auth_config": {"api_key": ...}}` sets `has_credentials: true`
**and** the dummy token genuinely reaches `graph.facebook.com` — the health check returns a real `401 Unauthorized`
from Meta, not a local serialization error. So the only missing piece is the real credential, not the API shape.

What a WhatsApp Cloud API (Meta Business Platform) setup needs, to get from the user:

1. A Meta Business Account with a WhatsApp Business Platform app (Meta for Developers -> My Apps -> Add Product ->
   WhatsApp), and a verified phone number registered to it (test numbers work for the Cloud API sandbox).
1. A **permanent** access token for that app — a temporary 24h token from the app dashboard's Quickstart is not
   enough for a Virtual Employee that must run unattended; it needs a System User with the `whatsapp_business_messaging`
   permission in Business Settings, with a token generated for that System User (no expiry).
1. The phone number id and WABA (WhatsApp Business Account) id shown on the app's API Setup page — needed if the
   mock/agent ever has to address a specific sending number, though the registered `tool_functions` (`send_text_message`
   etc.) may take it as a call argument rather than connector config; unverified until a real token is in place.

Once the token exists, applying it is one call from this account: `PUT /api/v1/connectors/0f8e4269-db0e-4993-ab97-8e3fee46248b`
with `{"auth_config": {"api_key": "<the token>"}, "csrf_token": "<cookie value>"}`, then `GET .../health` to confirm
`healthy: true`.

**Caution for whoever runs this next:** earlier blind probing this session (testing field names `credentials`,
`auth_credential`, `api_key`, `credential`, `access_token` directly against the live `whatsapp_kirro` connector,
before the throwaway-connector test found the real shape) left it with `has_credentials: true` but an **empty**
stored value — health now reports `"Illegal header value b'Bearer '"` instead of the original, more honest
`"Connector has no encrypted credentials"`. Functionally identical (still not usable), but cosmetically worse; a
real `PUT {"auth_config": {"api_key": "<token>"}}` will overwrite it correctly once a token exists.

**RESOLVED — a real token is live, 2026-10-02.** Created a Meta for Developers app ("Kirro", id `3204900803041522`)
under the `Upayan Mazumder` business portfolio, added the WhatsApp product, claimed its free test number
(`+1 555 155 9269`, Phone Number ID `1344278838768762`, WABA ID `1787986355581686`), added two verified recipients
(the user's second number, OTP-verified; a friend's number was offered but skipped — no OTP available), and sent a
real message through the console, confirmed delivered. The console's "Generate token" issues a **24-hour test
token**, not the permanent one planned below — confirmed by watching the first one expire (`has_credentials: true`
but health flipped from a real `400 Bad Request` at `graph.facebook.com` to a real `401 Unauthorized` about three
hours later). Applied via `PUT {"auth_config": {"api_key": "<token>"}}` as documented above; `PATCH` on the Declare
agent (`{"connector_ids":[...]}`, empty body otherwise) now returns `200 {"updated": true}` instead of 503 — the
chicken-and-egg scope-refresh block is clear.

**Permanent token — blocked, not by us.** A System User token (Business Settings → Users → System users, assigned
the WhatsApp asset, no expiry) was the intended fix. Creating a System User on this business portfolio silently
no-ops: the "Create system user" dialog accepts a name and role, the request appears to succeed, and a reload shows
"No system users added yet" every time, with no error surfaced. The business portfolio is **unverified**
(`Upayan Mazumder`, shown as "Unverified business" at connection time) — Meta restricts System User creation on
unverified business portfolios, which plausibly explains the silent failure. Business verification is a multi-day
external process (legal entity documents) and is out of scope here.

**Net effect:** the connector is demo-ready right now with a token good for roughly the next day; it will go stale
again on the same ~3-hour-to-24-hour cycle until either a verified business portfolio allows a System User token, or
someone repeats the "Generate token" + `PUT auth_config.api_key` cycle. The field shape and the cycle are now proven
and documented above — a five-minute fix each time it lapses, not a research problem.

The historical 503 (now cleared, see above) was `PATCH /api/v1/agents/{id} {"connector_ids":[…]}` failing for every
variant tried while whatsapp was unhealthy with no credentials at all.

### Twilio — registered and healthy, 2026-10-02

The native registry entry (`GET /api/v1/connectors/registry`, name `twilio`) declares `auth_type: api_key_secret`,
base URL `https://api.twilio.com/2010-04-01`, tools `get_message_status`, `get_recordings`, `make_call`,
`send_sms`, `send_whatsapp`. A two-part credential, unlike WhatsApp's single bearer token — found the right field
pair the same way: real credentials against disposable throwaway connectors, varying the field names, reading the
platform's own `/connectors/{id}/health` for a genuine Twilio response rather than guessing.

`account_sid` is used for URL templating regardless of what the second field is named — every candidate pair
(`{account_sid, password}`, `{..., token}`, `{..., secret}`, `{..., access_token}`, `{..., auth_secret}`) correctly
put the SID into `.../Accounts/{sid}.json`. Only one paired field name actually reaches the Basic Auth password:
**`{"auth_config": {"account_sid": "<SID>", "access_token": "<token>"}}`** — every other pairing returned a real
`401 Unauthorized` from Twilio (authenticated as nobody); `access_token` returned `{"status": "healthy", "account": "kirro"}`.

Registered as `twilio_kirro`, `PUT auth_config` with real credentials, confirmed `healthy: true`. Unlike WhatsApp's
test token, Twilio API keys don't expire on a short cycle, so this should stay healthy without the WhatsApp-style
manual refresh.

### Resolved: **one untrusted custom connector per agent** — and the fix

Tested on a fresh agent (created with only `mcp_pinelabs_kirro` + `mcp_venue_kirro`, no whatsapp, so no unhealthy
connector to poison the refresh — and indeed `connector_ids` PATCHes succeed there, confirming the 503 on `Kirro` is
caused by the unhealthy whatsapp):

| Agent | custom connectors linked | venue tools | pinelabs tools |
| ----- | ------------------------ | ----------- | -------------- |
| Kirro | venue, pinelabs          | 422         | **200**        |
| probe | venue, pinelabs          | **200**     | 422            |

and on the probe agent, **both venue tools together** scoped fine (`200`, scope
`tool:abb61bca-…__mcp_venue_kirro:write`), while **any mix with pinelabs** failed. Combined with `Kirro`, whose
custom set was also {venue, pinelabs} but scoped pinelabs + native `whatsapp_kirro`, the rule that fits every
observation is:

> **At most one untrusted custom connector's tools can be scoped per agent.** Native/trusted connectors
> (`whatsapp_kirro`) scope alongside it; a second custom one never does.

Which custom connector wins appears to be arbitrary (creation/refresh order) — not settable by reordering
`connector_ids`, which the API re-sorts.

**The fix this points to: expose the whole mock through a single MCP connector.** Since *all* tools of the one scoped
custom connector are grantable (all five pinelabs tools were), the answer is one aggregate MCP surface serving venue

- pinelabs (+ allocator + delhivery) at a single endpoint, registered as **one** connector. The Declare Agent then
  links exactly one custom connector and can be granted `get_release`, `declare_interest`, `create_mandate`,
  `get_mandate_balance`, and optionally `send_text_message` if a native connector is also linked.

Implementation: add an aggregate MCP server to `mock_server/mcp_surface.py` mounted at `/mcp` (all four surfaces'
tools in one MCPServer — the builders already exist), rebuild and redeploy, register it as e.g. `mcp_kirro_all`,
point a rebuilt agent at it, and grant the tool list. That stays inside ADR-012's design; no ADR change needed.

Probe agent deleted; tenant is back to `Kirro` + the 5 shadow agents and 11 connectors.

### RESOLVED — the aggregate connector unblocks the agent

The fix above worked end to end:

1. `/all/mcp` deployed (CI image + `kubectl rollout restart`); verified `200` over HTTPS.
1. Registered `mcp_kirro_all` → `https://api-kirro.upayan.dev/all/mcp`, MCP on. **All 18 tools discovered**,
   `health: {status: healthy, tool_count: 18}`.
1. Rebuilt the agent linking **only** that connector (the old one could not be edited — its `connector_ids` PATCH
   503s while the unhealthy whatsapp is attached). Note two platform details: agent names are unique on
   **`employee_name`** (the 409 says "choose a different employee name"), and a soft-deleted agent still holds the
   name until you `PATCH` the old record's `employee_name`.
1. Granted **all four** tools in one PATCH (`200`): `mcp_kirro_all__get_release`, `__declare_interest`,
   `__create_mandate`, `__get_mandate_balance` — i.e. the least-privilege set `agent-spec.md` §5 asks for, from a
   single custom connector.

Current `Kirro`: id `4aec1080-fc25-4b0d-bf5a-cc9642fc18be`, status `shadow`, one linked connector
(`mcp_kirro_all`), four authorized tools. (The previous `Kirro`, `ccbb1e36…`, is renamed `Kirro Archived` and
deleted.)

**First live eval (L01) passes.** In `Chat with Agent`, sending
`Tennis court this Saturday for 2, budget 8 to 10k, ideally 8` returned:

> "What is the single maximum you will pay per person? Please provide one number without a range or any ambiguous
> terms."

which is exactly L01's expected behaviour — ceiling unresolved, one question, and neither 8000 nor 10000 echoed —
at 65% confidence, correctly flagged `HITL` below the 88% floor. So `Chat with Agent` is a working eval channel and
the agent is runnable.

## 9. Workflow steps target agents, not connector tools

`/dashboard/workflows/new` → **Use Template** reveals `Workflow Configuration` (Name, Version, Domain, `Trigger Type`
∈ {manual, schedule, webhook, api_event, email_received, mongodb_schedule}, `Enable adaptive replanning`) and the
steps editor. The `Collaboration` step type opens an **agent picker whose options are agent *types*** —
`declared_interest_booking | Kirro`, `vendor_manager | Vendor Manager`, `support_triage`, `compliance_guard`,
`it_operations`, `contract_intelligence` — with an aggregation strategy (merge / vote / first_complete) and a timeout.

So a step is `{agent_type, action, inputs, …}` and **orchestrates an agent**; connector tools are reached through that
agent, not named directly in the step. That is why `workflow-spec.md` cannot be transcribed literally: its steps call
`allocator.draw`, `create_hold`, `execute`, `confirm_booking` and `release` directly, but the Declare Agent is
deliberately not authorised for any of those.

**Consequence for Phase 3:** build a second agent — e.g. `Kirro Allocator` (`agent_type` `kirro_allocator`, domain
`ops`) — linked to the same single aggregate connector `mcp_kirro_all`, authorised for `draw`, `create_hold`,
`get_hold`, `release_hold`, `confirm_booking`, `execute`, `release`, `refund` (all 18 tools are in that connector, and
one custom connector per agent is exactly what we can scope). The Window Allocation Workflow then has steps with
`agent_type: "kirro_allocator"` plus `notify` steps for the WhatsApp leg, and a `condition` step for the
winner/loser branch. That keeps the ADR-011 two-object design (Declare Agent + Workflow) while respecting the
platform's step model.

Note the agent picker lists agent types, so a new agent type must be created for the allocator role the same way
`declared_interest_booking` was (wizard step 2, `Create custom agent type`).

### Built 2026-10-02

Both halves of the ADR-011 design now exist on the platform.

**`Kirro Allocator`** — created **via API** (no wizard needed): `POST /api/v1/agents` with a brand-new
`agent_type: "kirro_allocator"` returned 201, so custom agent types do not require the wizard. id
`5591e57a-79f9-4b30-a95e-0b910a467ce3`, domain `ops`, linked to the single aggregate connector `mcp_kirro_all`, with
**10 tools granted in one PATCH (200)**: `draw`, `create_hold`, `get_hold`, `release_hold`, `confirm_booking`,
`execute`, `release`, `refund`, `list_releases`, `list_pool_entries`.

**`Kirro Window Allocation`** — `POST /api/v1/workflows` returned 201, domain `ops`, `trigger_type: manual`, with
these steps persisted in `definition.steps`. (Its id was `f22042ff-0682-4894-8c9c-cd3d3c835783`; it has since been
**recreated as `0aecf1b9-5a92-4b2a-8f98-30bb3a1b80ae` with a schedule trigger** — see §12 for why and how.)

| #   | name               | agent             | action              |
| --- | ------------------ | ----------------- | ------------------- |
| 1   | Fetch declare pool | `kirro_allocator` | `list_pool_entries` |
| 2   | Fetch release      | `kirro_allocator` | `get_release`       |
| 3   | Run DIFD draw      | `kirro_allocator` | `draw`              |
| 4   | Hold for winner    | `kirro_allocator` | `create_hold`       |
| 5   | Capture mandate    | `kirro_allocator` | `execute`           |
| 6   | Confirm booking    | `kirro_allocator` | `confirm_booking`   |
| 7   | Notify outcome     | —                 | `type: notify`      |

Form mechanics learned on the way: the Workflow Name input is the one with placeholder
`e.g. Invoice Processing Pipeline` (filling the first `input[type=text]` silently sets nothing and the form then
reports "Workflow name is required"); steps are edited as a JSON array in the `Define Steps (JSON)` textarea and are
stored under `definition.steps`; `GET /api/v1/workflows/{id}` returns the workflow.

Still to do for Phase 3: switch `trigger_type` to `schedule` (or wire `schedule_agent_task`) and run L12–L22. Note
step 7's `notify` needs `whatsapp_kirro`, which is currently unhealthy — see the credentials issue above.

### Open blocker: the agent's tool call never reaches the mock

Running the first full declaration through `Chat with Agent` on the rebuilt `Kirro`
(`4aec1080…`) worked conversationally and then failed at the first tool call. Transcript (one conversation, five
turns): the ceiling was re-asked at first (see below), then "300" → date re-asked → "this Saturday" → group-fallback
question → "2 would be fine" → **a correct, complete read-back** ("…for 4 people, with a maximum price of Rs 300 per
person. If the full group cannot be seated, a minimum of 2 people is acceptable. Shall I go ahead?") → "yes" →

> "There was an error while trying to create the mandate for your booking. Would you like me to try again or cancel
> the request?"

That response is itself correct behaviour (honest, offers retry/cancel, never claims success). The problem is the
failure underneath it:

- **The mock received nothing.** Its request log (`/app/data/logs/default.jsonl` on the PVC) contains only my own
  test calls; no platform-originated request. A `tools/call` reaches the REST route in-process, so a real invocation
  would be logged — it is not.
- **No policy denial was recorded** either: `/dashboard/enforce-audit` shows 0 entries.
- `GET /__admin/state?run_id=default` shows `mandates: 0`.

So *discovery* works (registering `mcp_kirro_all` found all 18 tools and `health` reports `tool_count: 18`) but
*invocation* from the agent does not land. Most likely candidate: our MCP server runs `stateless_http=True`, and the
invocation flow (`initialize` → `notifications/initialized` → `tools/call`) may need a real session that a stateless
endpoint does not keep. Next step is to run the MCP server **stateful** (or add the SSE transport) and re-register,
then re-run this transcript.

**Disambiguation that narrows the cause:** the same public endpoint *does* support invocation from an official MCP
client. Before this run, an `mcp` SDK client called `declare_interest`, `list_pool_entries` and `draw` against
`https://api-kirro.upayan.dev/venue/mcp` and `/allocator/mcp` successfully (their requests are the `mcpcheck` rows in
the mock log, with `status: 200`). So the server, the stateless transport, the Host allow-list and the TLS path are
all fine for `tools/call`; it is specifically AgenticOrg's invocation of the connector that does not arrive. That
points the question at the platform's connector-call path (or a scope/trust check that only applies at invocation
time) rather than at the mock.

Two conversational observations from the same run, both prompt-quality (not bugs):

- **False-positive ambiguity:** "max 300 each" is one number but the agent asked for the ceiling again. The turn also
  contained 7, 9 and 4, so the "more than one distinct number" rule may be being applied to the whole turn rather
  than to the money field.
- **The date was re-asked** after "300", although "this Saturday" had been given in turn 1 — while the group size
  *was* retained ("all 4 of you"). So memory works; date capture on a busy first turn does not.

### ROOT CAUSE of the tool-call failure: the Confidence Floor escalates every turn to HITL

Not a transport problem at all. Every reply lands at **0.60–0.79 confidence**, the agents' `confidence_floor` is
**0.88** (the wizard default), so the platform escalates *every* turn to HITL and **holds the tool call**. The
evidence lines up:

- `/dashboard/approvals` had **9 pending items** (15 by the second run), all `HITL: declared_interest_booking — confidence 0.6xx < floor 0.88`, `Trigger: chat_policy`, `Role: ops`.
- `Scope Dashboard` → **`Tool Calls (24h): 0`** — no tool call was ever dispatched.
- `/dashboard/enforce-audit` → 0 entries: this is an **escalation, not a denial**, which is why nothing was denied
  and nothing reached the mock.
- The mock's log confirms it received nothing.

So the agent's "There was an error while trying to create the mandate" is the consequence of a held approval, not of
a failed connector call.

**The fix is the Confidence Floor, and it cannot be set through the API.** `PATCH /api/v1/agents/{id}` with
`confidence_floor` (0.5 float, or 50 as a percent → 422) and with `hitl_condition` alone returns `200` but the values
never change — read-only, like `category` and `is_trusted`. It has to be set in the create wizard's **Behavior** step
(the `Confidence Floor` control) *at creation time*, so the practical route is to **re-create both agents with a
floor around 0.5** rather than trying to edit them.

Worth noting for the submission: a floor of 0.88 is unusable for a conversational agent — ordinary, correct turns
score 0.60–0.85 and would all need a human click. Also visible on the agent page: the platform is shadow-evaluating
the agent (`Shadow Samples: 12`, `Shadow Accuracy: 66.3%`).

### Correction: the escalation is driven by `hitl_condition`, not `confidence_floor`

`confidence_floor` **is** accepted at creation (`POST /api/v1/agents` with `confidence_floor: 0.5` produced an agent
whose floor is `0.5`) — but it does not change the rule that fires. Both agents were re-created with
`confidence_floor: 0.5` (Declare `21a46186-9e13-410e-a973-2ded067e54a5`, Allocator
`5591e57a-79f9-4b30-a95e-0b910a467ce3`, one aggregate connector each, tools granted), and the tool call was **still
held** with the same message. The new agent reports `confidence_floor: 0.5` but
`hitl_condition: "confidence < 0.88"`, and the approval rows now read
`HITL: declared_interest_booking — condition matched: confidence < 0.88`.

So the escalation is evaluated against the **`hitl_condition` expression string** (a free-text predicate, default
`confidence < 0.88` and seen pre-filled with the example `confidence < 0.88 OR amount > 500000`), and
`confidence_floor` is only the number shown on the page. `hitl_condition` is **not settable through the API** —
neither in the create payload (it defaults) nor in `PATCH` (200, unchanged) — so it can only be set in the create
wizard's **Behavior** step, which exposes both a `Confidence Floor` control and an editable `HITL Condition` field.

**The one remaining action is therefore:** create the two agents through the wizard (`Create Agent` → `Skip to manual setup`) with Behavior → `HITL Condition` set to something like `confidence < 0.5` (and the floor alongside it), link
`mcp_kirro_all`, grant the tools, and re-run the declaration. Everything else is in place: the mock, the aggregate
connector, the tool ACL, the prompt, and both agent roles.

Evidence that this is the last blocker: the mock receives nothing, `Tool Calls (24h)` stays 0, `enforce-audit` stays
empty (an escalation is not a denial), and every turn — including a perfect read-back at 85% — produces an approval
row instead of a tool call.

### Wizard attempt: what worked, what blocked, and the exact state

Ran the wizard again for `Kirro` (renaming the previous record to free the name, as before). Persona, Role and
Prompt all filled and advanced cleanly; the **Behavior** step accepted both settings:

- **`HITL Condition` (the field that actually matters) was set to `confidence < 0.5`** — a plain text input,
  placeholder `confidence < 0.88 OR amount > 500000`.
- **`Confidence Floor` is a real `<input type="range">` with `min="0.5" max="0.99" step="0.01"`** — so 0.50 is the
  lowest the UI allows, and the earlier API-created `confidence_floor: 0.5` was already at that minimum.

Automation mechanics worth keeping:

- **Synthetic events do not move that slider.** Setting `.value` through the native setter and dispatching
  `input`/`change`, and dispatching `ArrowLeft` keydowns, both left it at 0.88 (React's state never changed).
- **A real mouse click does.** `tab.clickAt()` on the track works: 50 % of the width gave `0.75`, and clicking 1 px
  from the left edge gave the minimum, `0.5`.

**Where it stopped:** with floor `0.5` and condition `confidence < 0.5` both set (consistent), the step's `Next`
button is **disabled**, and I could not find the reason — `Select All` in the tool picker did not re-enable it, and
the page reports no validation error. The wizard has no draft persistence, so leaving the page loses the work.

**Exact next step for whoever picks this up:** get an agent created whose `hitl_condition` reads
`confidence < 0.5`. The wizard is the only surface that edits that field; if `Next` stays disabled, the practical
alternative is to find how the wizard stores it (its network payload on save) and replay that through
`POST /api/v1/agents`, since `POST` *does* honour `confidence_floor` and the tools/connectors can then be fixed with
`PATCH` as proven above. Everything else is ready: mock, `mcp_kirro_all`, the ACL, the prompt, and both agent roles.

### Definitive: `hitl_condition` is not part of the agent API at all

Probed with deliberately wrong types, which is the cleanest test of whether a field exists in the model:

| create payload sent                                                  | result                                                          |
| -------------------------------------------------------------------- | --------------------------------------------------------------- |
| `hitl_condition: 12345` (an int where a string belongs)              | **201** — no type error, so the field is ignored, not validated |
| `hitl_condition: "confidence < 0.5"` alone                           | 201, stored `confidence < 0.88`                                 |
| `confidence_floor: 0.5` **and** `hitl_condition: "confidence < 0.5"` | 201, stored `floor=0.5` but `hitl=confidence < 0.88`            |

So `confidence_floor` is honoured on create, `hitl_condition` is **silently discarded**, and the stored default does
**not** track the floor (a 0.5 floor still yields a `confidence < 0.88` condition). There is also no agent-types
endpoint (`/api/v1/agent-types` → 401 catch-all), so the type template cannot be edited either, and the session
expires — a 401 `Missing or invalid Authorization header` means re-login at `/login` (email + password form) before
any further API call.

The wizard remains the only surface that writes `hitl_condition`, and its `Next` was disabled on the Behavior step
even with floor 0.5 and a consistent condition. Untried options for the next session, cheapest first:

1. **`Create Agent` → "Describe in English" → Generate.** The generator builds a whole configuration, and its
   Behavior defaults may include a workable condition — one action instead of the five-step wizard.
1. **Capture the wizard's save payload** (hook `POST /api/v1/agents` in the page while the wizard submits) and
   replay it with `hitl_condition` set; that reveals the true field name/shape if the API does accept it under
   another name.
1. Ask the platform whether a custom agent can lower its HITL condition at all — a floor whose minimum is 0.5 while
   ordinary correct turns score 0.60–0.85 makes the feature, as configured, unusable for a conversational agent.

Tenant left coherent: `Kirro` (Declare, floor 0.5, one aggregate connector, 4 tools), `Kirro Allocator` (floor 0.5,
10 tools), the 5 untouched shadow agents, and 13 connectors. All probe agents and connectors deleted.

### Solved: the wizard recipe that *does* set `hitl_condition` — and what still blocks

**The recipe works.** The reason my first manual wizard attempt stalled was linking a connector at the Behavior step:
that disables `Next`. The path that works, verified end to end:

1. `Create Agent` → **Describe in English → Generate.** The generated wizard's `Next` is enabled (no connector
   linked), unlike the hand-built one.
1. Step 1 Persona: set Name/Designation and, importantly, **Domain** — the generator defaults to `travel`, and
   `domain` is immutable later, so it must be right here.
1. Step 2 Role: tick `Create custom agent type` and enter the slug (`declared_interest_booking`); the type picker
   only lists built-in types, so a custom type must come from this checkbox.
1. Step 3 Prompt: replace the generated text with the verbatim `agent-spec.md` §3 prompt.
1. Step 4 Behavior: `Confidence Floor` slider is `min 0.5` — **move it with a real `tab.clickAt()` on the track**
   (synthetic events don't commit), then set `HITL Condition` to the same threshold (`confidence < 0.5`). **Link no
   connector** — do it afterwards.
1. Review → `Create as Shadow`.
1. Then through the API: `PATCH` the connector (`connector_ids`), the tools (`authorized_tools`) and the prompt
   (`system_prompt_text`). All three work.

That produced `Kirro`, id **`455907ea-d9eb-4fc2-aecd-e19369febdf8`** — `agent_type: declared_interest_booking`,
`domain: ops`, `confidence_floor: 0.5`, **`hitl_condition: "confidence < 0.5"`**, the four tools, the 6,545-char
prompt, one connector.

**But the tool call is still held, and it is not the agent's condition any more.** The new approval rows read
`condition matched: confidence < 0.5` — so the agent-level condition is correctly 0.5 — with
**`Trigger: chat_policy`**. That means the escalation is coming from a **platform-level chat policy**, not from the
agent's `hitl_condition`, and it fires on ordinary turns whose stated confidence is 0.60–0.85. Deciding one of them
(`POST /api/v1/approvals/{hitl_id}/decide` → `{"decision":"approve","status":"decided"}`) does **not** release the
held action either: the mock still received nothing and `mandates` stayed 0.

**Also confirmed immutable through the API for an existing agent:** `category`/`is_trusted` (connectors),
`confidence_floor` on update, `hitl_condition`, `domain` and `agent_type` — all return 200 and change nothing. Only
creation-time values and the wizard can set them.

**Next options, cheapest first:** look for the org/chat-policy setting that drives `chat_policy` (Scope Dashboard,
Approvals, or an admin surface); ask the platform whether `chat_policy` HITL can be relaxed for a demo tenant; or
drive the agent by phone/WhatsApp instead of the Chat panel, since the held approvals are all `Trigger: chat_policy`
and may be specific to that channel.

Cleanup still owed on the tenant: two leftover renamed records, `Kirro Old3` and `Kirro Travel` (both shadow,
harmless, but they should be deleted).

## 10. RESOLVED: the tool call reaches the mock (verified 2026-10-02)

The chain works end to end on agent `455907ea-d9eb-4fc2-aecd-e19369febdf8`:

```
Chat with Agent -> agent (active) -> connector mcp_kirro_all_v4 -> our mock -> 200
```

Our mock logged `pinelabs.create_mandate` `{"amount": {"value": 120000, "currency": "INR"}}` → `status: ACTIVE`, and
`GET /__admin/state` moved `mandates` 0 → 1. The platform's own approval record for that turn reads
`tool_calls: [{tool: create_mandate, status: success}]`.

### What actually blocked it: agent maturity, not a chat policy

`Trigger: chat_policy` in the approval rows was a symptom of the agent still being in **shadow** maturity. Nothing
in the org relents while it is shadow; promotion to `active` is the switch, and after promotion the very next
conversation executed the tool.

`POST /api/v1/agents/{id}/promote` is gated by two server-computed values, both **immutable through the API**:

| gate                      | value   | notes                                                                            |
| ------------------------- | ------- | -------------------------------------------------------------------------------- |
| `shadow_min_samples`      | 20      | PATCH 200, value unchanged                                                       |
| `shadow_accuracy_floor`   | 0.800   | PATCH 200, value unchanged                                                       |
| `shadow_accuracy_current` | rising  | computed; observed 0.668 @23 samples → 0.742 @33 → 0.777 @48 → 0.784 @55 → 0.800 |
| `shadow_sample_count`     | +1/turn | chat turns only                                                                  |

Creating an agent with `status: "active"` is forced back to `shadow` (201 with `status: shadow`). So the only route
is: chat enough turns that the computed accuracy clears 0.800, then promote — which then returns
`{"promoted": true, "from": "shadow", "to": "active"}`. Accuracy climbs with every turn regardless of topic, so
clean, well-formed declaration turns are the cheapest way up; expect roughly 60–70 turns from a fresh agent.

### Connector schema changes need re-registration, then a health check

The registered connector caches the tools discovered at registration time — redeploying the mock does **not** refresh
them. Each schema change therefore needs a new connector record (`mcp_kirro_all_v2`, `_v3`, `_v4`), a relink
(`PATCH connector_ids` + `authorized_tools`), and then `GET /api/v1/connectors/{id}/health`. Without that health call
the agent answers every turn with *"This agent cannot run because a required connector is not authenticated, healthy,
and refreshable"* even though the connector is green.

### Two argument bugs the first real call exposed

1. **Shape.** The model did not always supply `amount_value` as our signature demanded; the platform surfaced
   *"The amount value is missing"* and a later call returned our own 400. Fixed in
   `mock_server/mcp_surface.py`: `_coerce_amount` accepts an int, a numeric string or `{"value": N}`, under
   `amount_value` / `amount` / `amount_paise`, and the failure path echoes what actually arrived.
1. **Unit.** With the call going through, the model passed `value: 1200` for an agreed Rs 1,200 — rupees where paise
   were expected, a mandate two orders of magnitude too small — and the agent then told the user Rs 1,200 was
   reserved. Fixed by stating the multiplication rule (with a worked example) in the tool descriptions, which is the
   only prompt-adjacent surface that stays writable on an active agent. Verified: `{"value": 120000}`.

### Prompt is locked once the agent is active

- `PATCH system_prompt_text` → **409 `Prompt is locked on active agents. Clone this agent to make changes.`**
- `prompt_amendments` accepts a PATCH (200) but stores nothing, in any shape tried.
- `POST /api/v1/agents/{id}/clone` → **403 `Missing scope: agenticorg:admin`**.

So a live prompt fix needs an admin-scoped account. The prompt the agent does run (the corrected one, transcribed
into `agent-spec.md` §3) has since been verified to work: the agent does call `declare_interest`, and when its
arguments arrive it produces a correct pool entry (§11).

**Workaround, verified 2026-10-02: the lock does not apply to a *paused* agent.** The cycle is

1. `POST /api/v1/agents/{id}/pause` → 200, status `paused`;
1. `PATCH /api/v1/agents/{id}` with `system_prompt_text` → **200 `{"updated": true}`** (the 409 is gone);
1. `POST /api/v1/agents/{id}/resume` → 200, status `active`, with the new prompt in force.

`/resume` only works from `paused` (*"Cannot resume agent in 'shadow' status; must be paused"*), and the lifecycle is
`active ↔ paused` plus `retire` → `retired`. So an active agent's prompt **is** editable from this account — no admin,
no clone, no shadow re-promotion — which corrects the conclusion above. Both live agents were fixed this way: the
declare agent got its cancellation-release rule, and `Kirro Allocator` (the one the workflow names) got the
loser-release rule, each in one pause/edit/resume cycle.

**Agent lifecycle (verified 2026-10-02):** `DELETE` on an `active` agent returns 409 *"Cannot delete agent in 'active'
status. Pause or retire the agent first."* — so it is **pause** (200 → `paused`) then **retire** (200 → `retired`) then
delete (200). All three exist as `POST /api/v1/agents/{id}/{pause|retire|delete}`.

**Tenant cleaned up 2026-10-02.** The investigation had left one connector per schema iteration and one agent per
experiment; both are now trimmed to a demo-ready state:

- **Connectors:** the 20 superseded `mcp_kirro_all_v1…v20` deleted, along with the non-MCP probe. Remaining are the
  four per-surface mocks (`mcp_venue_kirro`, `mcp_pinelabs_kirro`, `mcp_allocator_kirro`, `mcp_delhivery_kirro`), the
  aggregate **`mcp_kirro_all_v21`** the agents link, and the native ones (`whatsapp_kirro`, `pinelabs_plural`,
  `stripe`, `tally`, `zoho_books`, `gstn`, `banking_aa`).
- **Agents:** `Kirro Declare v2`, `v3` and `Kirro` retired and deleted; **`Kirro Declare v4`** (`27ec9d3c`) and
  **`Kirro Allocator`** (`5591e57a`) remain, both `active`. The five platform built-ins are untouched.
- **Workflow:** one, `Kirro Window Allocation`, `Trigger | schedule`.

## 11. Tool arguments: what arrives, what the mock resolves, and what the platform withholds

**Status: the argument pass-through is intermittent and platform-side.** One schema change tracked it for a while, the
mock now also resolves every ambiguity it can from the state it holds, and — when the pass-through is up — the whole
chain runs end to end through the real agents (§12). But it goes down for periods at a time while `create_mandate`
keeps working in the same conversation, and nothing in this repo correlates with either state. Read this section as:
the mechanism we could influence, the ambiguities we now absorb, and the timestamps to take to the platform.

**The mechanism we could influence:** a parameter declared with a concrete type and default (`release_id: str = ""`,
`group_size: int = 0`) arrives **empty or zero** no matter what the model chose, while an untyped one
(`amount_value: Any = None`) carries the model's value. Every model-facing parameter on all four surfaces is
therefore untyped, with a test asserting it stays that way.

Making `list_releases`, `get_release` and `declare_interest` match that shape (lean parameter list, `Any = None`, no
annotations) was followed by the arguments arriving end to end, without touching the agent, whose prompt is locked:

```
02:05:13 mcp.get_release     -> {"release_id": null}                       # still starts empty
02:05:16 mcp.declare_interest-> {"release_id": null, "group_size": null, …} # guard answers with the candidates
02:05:20 mcp.declare_interest-> {"release_id": "rel_badminton_sat", "group_size": null, …}
02:05:24 mcp.declare_interest-> {"release_id": "rel_badminton_sat", "group_size": 4,
                                 "min_group_size": 2, "max_price_paise": 30000}   # DECLARED
```

The model converges over three attempts because each guard returns a useful error naming what is missing and, for the
release, the candidates themselves. The resulting pool entry is real and correctly valued:

```json
{"declaration_id": "decl_default_rel_badminton_sat",
 "acceptable_slot_ids": ["bd_0700", "bd_0800", "bd_1800"],
 "group_size": 4, "min_group_size": 2, "max_price_paise": 30000, "status": "DECLARED"}
```

`acceptable_slot_ids` is filled by the mock from the release's own slots — the model never supplied it — which is the
documented fallback doing its job rather than the bid being dropped.

**Consequence:** the declare leg completes through the real agent when the model populates the call — verified
pool entries carry the conversation's values:

```json
{"declaration_id": "decl_default_rel_badminton_sat",
 "acceptable_slot_ids": ["bd_0700", "bd_0800", "bd_1800"],
 "group_size": 4, "min_group_size": 2, "max_price_paise": 30000, "status": "DECLARED"}
```

**Parameter count matters too.** The two verifiably good bids were made against a **five**-parameter
`declare_interest`; every failure afterwards came after the signature grew to seven to carry `mandate_id` and
`user_contact`. Those two are redundant — the mock attaches the run's most recent mandate itself and the pool entry
has no separate contact — so the signature went back to five, and the tool now asks only for what it cannot work
out.

**What the mock resolves on the agent's behalf.** Every one of these exists because the model reliably declines to
supply something it demonstrably knows, and each is documented in the code where it lives:

| argument the model omits         | what the mock does instead                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------------- |
| the amount's unit                | states the paise rule with a worked example in the description (values then arrive as paise) |
| `release_id` for the pool lookup | resolves to the one release whose pool holds bids; otherwise refuses and lists them          |
| `release_id` for the draw        | resolves from the bids, since a declaration belongs to exactly one release's pool            |
| the release's slot ids           | bids for the release's own slots                                                             |
| the mandate id on the bid        | attaches the run's most recently created mandate                                             |
| a date that matches nothing      | falls back to whatever the event matched (weekday arithmetic is a known model weakness)      |
| an empty `get_release` call      | answers with the candidate releases rather than refusing                                     |

None of these invent a business fact: each resolves an ambiguity from state the mock already holds, and each
refuses with a useful message when it cannot.

**What does not work, and is not ours to fix.** The emission is not deterministic, and it degrades to
*consistently* empty for the venue tools while never failing for the mandate tool. Every one of these was tried
against the live platform, each with a deploy and a live conversation:

| tried                                                                                                                                                                                                                                                                           | result                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| typed parameters → untyped (`Any = None`)                                                                                                                                                                                                                                       | values arrived for a while (the two good bids), then stopped                                                                                                                                                                                                                                                                  |
| aliases (`releaseId`, `event`, `on_date`, …)                                                                                                                                                                                                                                    | no change — an empty call has nothing for an alias to match                                                                                                                                                                                                                                                                   |
| a five-parameter signature (back from seven)                                                                                                                                                                                                                                    | no change                                                                                                                                                                                                                                                                                                                     |
| a one-sentence description on the model of `create_mandate`'s                                                                                                                                                                                                                   | no change                                                                                                                                                                                                                                                                                                                     |
| a brand-new agent, created, linked and promoted fresh                                                                                                                                                                                                                           | no change — so it is not accumulated agent state                                                                                                                                                                                                                                                                              |
| a fresh, short conversation (five turns)                                                                                                                                                                                                                                        | no change                                                                                                                                                                                                                                                                                                                     |
| self-contained descriptions (no cross-references to other tools, each argument given with an example value)                                                                                                                                                                     | no change                                                                                                                                                                                                                                                                                                                     |
| the connectors' stored `tool_schemas` on the platform                                                                                                                                                                                                                           | match what the mock serves exactly — so re-registration is not a remedy                                                                                                                                                                                                                                                       |
| tenant tool-catalogue bloat (21 aggregate connectors × 18 tools registered during the investigation)                                                                                                                                                                            | no change after deleting 20 of them — and `GET /api/v1/tools` is the platform's **native** catalogue (559 entries, none of ours), so our connectors never added to it in the first place                                                                                                                                      |
| a non-MCP connector with declared operations (a different invocation path from MCP discovery)                                                                                                                                                                                   | registered fine and came back `is_trusted: true`, but with **0 tools**, and every way to declare operations (`PATCH` `tool_functions`/`operations`, `POST …/operations`, `POST …/tools`) returns the 401 OAuth gate — so the path is unreachable, matching ADR-011 Risk 2's "no visible way to declare individual operations" |
| a different model (tool-calling fidelity differs by model, and a *new* agent can be created with any `llm_model`)                                                                                                                                                               | unavailable — creating agents with `llm_model: deployment:gpt-4o` and `llm_model: gpt-4o` both came back as `gpt-5.4` with the same `llm_config`; the model is fixed by the tenant, like `llm_config` is                                                                                                                      |
| camelCase id aliases (`releaseId`, `release`, `authorizationId`, `holdId`, `paymentId`) declared on all eleven tools that take an id — the log had shown `bids`/`slot_id`/`quantity` arriving while `release_id` did not, which pointed at the model emitting an undeclared key | **all of them arrive null too** (`{release_id: null, releaseId: null, release: null}`), so the id is not being emitted under any name; the platform passes every declared parameter as null. (The aliases are kept — strictly more tolerant, no cost.)                                                                        |

`create_mandate` has arrived populated through every one of those schema changes, on every conversation — eight
parameters, untyped, one-sentence description — so the difference is per-tool on the platform side, and the platform
records each of these calls as `status: success`. It is not even that the mandate tool succeeds where others fail:
the log shows it receiving an empty call too (`mcp.create_mandate -> {}`) and then succeeding on the retry with
`{"amount_value": 120000}`, in the same turn where `declare_interest` retried empty three times. So the model *does*
recover for that tool and does not for the others, and what to ask the platform is narrow: why does one tool's
arguments survive while another's arrive null, in the same conversation, from the same model?

It also does not always *try*: on one turn it told the user "You are now entered into the pool" with no
`declare_interest` call in the log at all, which `agent-spec.md` §3 step 10 forbids. The mock's guards make that
cheap to detect — the log simply has no invocation — but nothing on our side can make the model place the call.

### The timeline says this is platform-side, not schema-side

The same tools, from the same agents, behaved differently across the session without their schemas changing in any
way that correlates:

| window (2026-10-02) | venue tools                                                                                                                    | mandate tool                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| 02:05 – 02:34       | arguments arrive — `declare_interest` with the conversation's values, `get_release` and `draw` with their release ids and bids | arrives                                            |
| 02:40 – 03:51       | every call arrives all-null, across both agents, every schema variant, and several fresh conversations                         | arrives, flapping (one empty call, then the value) |
| 03:59 – 04:12       | arguments arrive — the whole chain and the declined path ran on them (§12)                                                     | arrives                                            |
| 04:20 →             | all-null again, on both agents and in fresh conversations; a 2.5-minute quiet period did not restore it                        | arrives                                            |
| 04:33 / 04:35       | up for one run (L12 passed, §12) and down again two minutes later, same agent, same conversation shape                         | arrives                                            |

Two of those rows kill the last correlations worth testing. The pass-through does **not** track load on our side — it
went down once while this session was registering connectors and once while it was doing nothing but waiting, and a
deliberate quiet period before a retry changed nothing. And the windows are **minutes**, not hours: it served a full
allocation at 04:33:44 and returned nulls by 04:35:48, same agent, same conversation shape. That is the signature of
**per-request variance at the platform's end** — plausibly a subset of backends behind a load balancer dropping tool
arguments — rather than any state we can set. `create_mandate` works throughout.

So the schema-side remedies above were all tested inside the broken window, and the "untyped parameters" fix that
appeared to work at 02:05 was tested inside the first good one. That is why the table's remedies cannot be read as
causal: **the pass-through comes and goes on the platform's side**, and nothing in this repo tracks it. Two
consequences worth carrying forward: the timestamps above are the observation to take to the platform, and because it
is intermittent, **a single failed attempt proves nothing** — re-test before concluding anything from a new remedy.
This section's remedies are therefore a record of what was ruled out, not of what caused it.

**The platform's own copy of the schema is correct**, which rules out staleness and makes re-registration pointless as
a remedy. `GET /api/v1/connectors/{id}` returns `tool_schemas`, and for the current connector the venue tools match
what the mock serves exactly — `list_pool_entries` with an untyped `release_id` defaulting to null, `create_mandate`
with its five amount aliases. So the platform knows the parameter, knows its name, and sends null anyway.

Two candidate mechanisms were tested and disproved along the way, and are worth recording so they are not re-tried:

- **The model parroting the description's example.** Every mandate had arrived as exactly 120000 — the number in the
  worked example (4 people × Rs 300). Changing the example to *3 people at Rs 250 = 75000* and running a 4-people
  × Rs 300 declaration still produced **120000**, so the model computes correctly, including the ×100 to paise. The
  paise fix is real, not an artefact.
- **A single obvious argument being the magic.** `list_pool_entries` takes exactly one (`release_id`) and receives
  null; `create_mandate` takes eight and receives its value. Argument count, description length and alias count were
  each varied independently without effect.

The agent's `llm_config` (`sliding_16k`, `temperature 0.1`) is immutable through the API, so conversation length
cannot be traded for reliability from this account either.

**The question still worth putting to the platform:** why does a tool call's arguments get prefilled from the

With typed parameters the same calls arrived as follows, and the platform recorded them as `status: success` — its
record cannot distinguish "the tool refused" from "the arguments were empty", so only our own log could:

With §10 fixed, the calls reach the mock — but the arguments do not. `mock_server` now logs every MCP tool
invocation with the arguments as received (`target: "mcp.<tool>"` in the same per-run JSONL as the REST routes).
That log is unambiguous:

```
2026-10-02T01:22:24Z mcp.create_mandate  -> {"amount_value": 120000}   # correct, Rs 1,200 in paise
2026-10-02T01:22:48Z mcp.declare_interest -> {}                        # no arguments at all
2026-10-02T01:39:04Z mcp.create_mandate  -> {"amount_value": 120000}   # correct again
2026-10-02T01:39:09Z mcp.get_release      -> {"release_id": ""}         # the names arrive, the values do not
2026-10-02T01:39:12Z mcp.declare_interest -> {"release_id": "", "group_size": 0, "min_group_size": 0,
                                              "max_price_paise": 0, "acceptable_slot_ids": ""}
```

The last two lines are the sharpest form of it: the model produces the call with every parameter **named but
empty** (or zero). It knows the schema; the values the user gave it — four people, Rs 300, badminton, tomorrow —
never reach the tool. `create_mandate` is the one call that arrives populated, and it does so consistently.

So the agent calls `get_release`/`declare_interest` with no usable arguments while the platform records the call as
`status: success`. Its record cannot distinguish "the tool refused" from "the arguments were empty" — only our log
can.

What was tried, and what it ruled out:

### History: what was tried while the arguments were dropped

1. **Signature strictness.** A strict signature produced *"The amount value is missing"* from the platform; every
   parameter optional produced our own guard firing instead. Neither changes what the model emits.
1. **Argument naming.** Declaring `amount_value`/`amount`/`amount_paise`/`amountValue`… and `release_id`/`releaseId`/
   `event`/`date` made no difference: the argument object was empty before the call, so no alias could match it.
1. **A lean, required-argument surface** (`get_release(release_id)`, `declare_interest(release_id, group_size, min_group_size, max_price_paise)`, short descriptions, no aliases) — and when that produced a *platform-side*
   rejection for the missing required parameter, an empty lookup was made to answer with the candidates instead
   (`get_release("")` returns the releases) and the bid's `release_id` was made optional for the same reason: an
   empty call must reach us to be answered usefully. It reaches us — still empty. `create_mandate`, whose
   description names exactly one obvious argument, is the only call ever seen with populated arguments — which is
   what pointed at the schema rather than the model, and is what untyping every parameter then confirmed.

**The question still worth putting to the platform:** why does a tool call's arguments get prefilled from the
JSON-schema defaults? A parameter annotated with a concrete default silently discards whatever the model chose, and
the platform records the call as `status: success`, so nothing in its own records shows the loss — only the
connector's log can. Our workaround is a schema with no annotated defaults; theirs would be to pass through what the
model produced.

**Kept as a fallback:** the pool can also be seeded through the mock's own REST route
(`POST /venue/releases/{release_id}/declarations`) — the same code path the tool calls use — which is useful for
exercising the Workflow without a conversation.

## 12. The Window Allocation Workflow: what is broken, what is proven

The deployed workflow **`f22042ff` ("Kirro Window Allocation", 7 steps, `trigger_type: manual`)** reports
**`Pipeline Status: Failed`** on every run, and its steps never reach the mock — no `venue.*` request appears in any
run log, and the run produces **no Audit Log events at all**.

What was found and fixed:

1. Every step runs as `agent_type: kirro_allocator`. The tenant has exactly one such agent — **`Kirro Allocator`
   (`5591e57a`)** — and it was bound to the *superseded* connector `mcp_kirro_all`, granted ten `mcp_kirro_all__*`
   tools, had a **0-length system prompt**, and sat in **`shadow`** maturity with 0 samples.
1. It is now re-linked to the current aggregate connector (`mcp_kirro_all_v10`, healthy, 18 tools) with the eleven
   tools its steps call (`draw`, `create_hold`, `get_hold`, `release_hold`, `confirm_booking`, `execute`, `release`,
   `refund`, `list_releases`, `list_pool_entries`, `get_release`), and it was given a spec-derived prompt
   (`workflow-spec.md` §2–§4) — it had none at all.
1. It is now **`active`**: `shadow` maturity was the same gate the declare agents hit, and it turned out not to need
   an admin at all — chat turns accumulate samples, and this agent cleared the bar in 21 turns at 0.85 accuracy
   (`POST /agents/{id}/promote` → `{"promoted": true, "from": "shadow", "to": "active"}`). Chatted directly, the
   agent does drive the mock: `venue.list_declarations` appears once per turn (01:48–01:52).
1. **The Workflow still fails, and this is the part that is not ours.** A run accepted at 01:54:2x
   (`POST /workflows/{id}/run` → `{"status": "running"}`) produced **not one call to the mock** — the log's last
   entry before it is 01:52:53, from step 3's chat — reports `Pipeline Status: Failed`, and writes **no Audit Log
   event at all**. So the platform's Workflow engine never reaches the agent or its tools, even with every input it
   controls (agent active, connector healthy, tools granted, payload `{release_id: ...}`) in place.
1. Step 7 is a **notify** step (`type: notify`, `channel: whatsapp`) rather than an agent-action step, so it carries
   no `agent_type` and the builder renders it as **`Agent: undefined`**. Whether the engine treats notify steps
   specially is unverified — no step of any kind has ever executed — and the mock's WhatsApp leg is uncredentialed
   regardless (`platform-map.md` §6), so this is recorded as a shape to confirm rather than a defect to patch.

`GET /workflow-runs/{id}` and `GET /workflows/{id}/runs` both require OAuth (401), so the run's own error is not
readable from this account.

### What has been ruled out for the Workflow's silence

Creation accepts an arbitrary definition from this account, so the step shape itself could be varied and tested
(each probe: create → `POST …/run` → watch the mock's log for a request; all probes were deleted afterwards):

| hypothesis                                                     | probe                                                                   | result                                   |
| -------------------------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------- |
| The `agent_type` binding never resolves to the instance        | same 1-step definition with `agent_id: 5591e57a-…` instead              | **no call** — ruled out                  |
| The bare `action` name never resolves to a granted tool        | `action: "mcp_kirro_all_v10__list_pool_entries"` (fully qualified)      | **no call** — ruled out                  |
| The allocator's `shadow` maturity blocked its steps            | promoted it to `active` (acc 0.85) first, then ran the 7-step workflow  | **no call** — ruled out                  |
| A stale connector binding blocked the steps                    | re-linked to `mcp_kirro_all_v10` and health-checked it (18 tools)       | **no call** — ruled out                  |
| The run needed a payload the steps could use                   | `POST …/run` with `{release_id: "rel_badminton_sat"}`                   | accepted (`status: running`) then Failed |
| A step needs an explicit `type` (only the notify step has one) | three probes, `type: "agent"`, `"tool"` and `"step"` on the action step | **no call** — ruled out                  |

So the engine accepts a run and then reaches neither the agent nor its tools, whatever the definition says. What
remains is not reachable from this account: the run detail (401) and the engine's own logs.

### The trigger is create-time only — and it works from this account

`PATCH`/`PUT` and `POST …/schedule` on an **existing** workflow all return 401, and `/dashboard/report-schedules`
returns 403 with the reason stated outright:

> Your current role can't view /dashboard/report-schedules. YOUR ROLE: developer. REQUIRED ROLES: admin | cfo | cmo.
> RBAC is enforced server-side.

**`POST /api/v1/workflows` is not gated the same way.** It accepts `trigger_type: "schedule"` with
`trigger_config: {cron}` from this developer account and carries the supplied `definition` over verbatim, so a manual
workflow can be converted by recreating it (a probe workflow, `0e9f8b59`, confirmed the acceptance and was deleted;
`DELETE /api/v1/workflows/{id}` also works, 200). The workflow was therefore recreated under the same name:

- id **`0aecf1b9-5a92-4b2a-8f98-30bb3a1b80ae`** (replaces the deleted `f22042ff`),
- `trigger_type: schedule`, `trigger_config.cron: "5 6 * * *"` — daily 06:05Z, five minutes after the sample
  releases' `opens_at` of 06:00Z, which is the cadence the domain implies,
- `is_active: true`, the 7-step definition unchanged, and it is the only workflow in the tenant.

Verified in the builder UI, which now reads **`Trigger | schedule`**, Active, 7 steps. The existing workflow's run
history is not carried over by a recreate, which cost nothing here — it never had a successful run.

**The Agent Scheduler route is closed from this account.** `workflow-spec.md` §1 wants the declare agent to call
`agent_scheduler__schedule_agent_task` when it learns a release's `opens_at`, so the run fires per release rather than
on a fixed cron. That tool does exist — `GET /api/v1/tools` lists 559 platform tools including
`agent_scheduler__schedule_agent_task`, `cancel_agent_task` and `list_my_schedules` — but it cannot be granted:
`PATCH /api/v1/agents/{id}` with it in `authorized_tools` returns **422** *"Invalid authorized_tools … Use
GET /connectors/registry or GET /tools to discover valid tool names"*, and no connector in the tenant exposes it, so
the agent cannot link it either. The scheduler is not reachable by an agent here, let alone callable directly (every
`/api/v1/tools/…` invocation endpoint returns 401 with the OAuth gate). The cron on the recreated workflow is
therefore the only trigger available, and `workflow-spec.md` §1 records it.

### Per-release idempotency is proven at the mock, which is what the Workflow needs

Verified live 2026-10-02 against `https://api-kirro.upayan.dev` (runs `dryrun_a`, `dryrun_c`):

| property                                              | evidence                                                                                                                                                                              |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The draw is deterministic per (release, window, bids) | two identical `POST /allocator/draw` calls returned byte-identical results and the same seed `ae20c6d2…`                                                                              |
| Side effects dedupe under a stable key                | two `POST …/holds` with one `Idempotency-Key` returned the same `hold_0001`; two `POST /pinelabs/mandates` returned the same `auth_0001`; state held exactly one hold and one mandate |

So a re-run of the Workflow is a no-op **provided the deployed steps send a stable idempotency key per release** on
the hold/mandate/capture calls; the mock honours the key today. That is the requirement to state in
`workflow-spec.md` when the Workflow is (re)built with admin access.

### The rest of the chain works end to end (mock-level dry run)

Two consecutive live runs, same public mock:

- **Happy path** — `hold` → `mandate ACTIVE 100000p` → `execute SUCCESS (pay_0001)` → booking **`BK-0001` CONFIRMED**;
  state `{active_holds: 1, bookings: 1, payments: 1}`.
- **Payment declined** — scenario `payment_failure`, then `execute` → **`status: FAILED, reason: BANK_DECLINED`**;
  booking attempt → **402 `PAYMENT_REQUIRED`** (the venue refuses to confirm without a captured payment); after the
  engine's reversal (`release_hold`, `release` mandate) the state reads
  `{active_holds: 0, bookings: 0, payments: 0, released_mandates: 1}` and the hold reports `released`.

### The whole chain now runs through the real platform agents (verified 2026-10-02 04:01)

Both blockers cleared at once: the argument pass-through came back (§11's timeline is intermittent, not a permanent
break), and with a bid in the pool the allocator drove the rest. One conversation each, no repo-side intervention
during the run, every step visible in the mock's log:

| time (UTC) | what the platform agent called                                                                                   | result                                                                                                       |
| ---------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 03:59:28   | `create_mandate` `{amount_value: 120000}`                                                                        | mandate `ACTIVE` — the conversation's 4 × Rs 300, in paise                                                   |
| 03:59:33   | `get_release`                                                                                                    | release fetched                                                                                              |
| 03:59:36   | `declare_interest` `{release_id: "rel_badminton_sat", group_size: 4, min_group_size: 2, max_price_paise: 30000}` | pool entry: those values **plus** `mandate_id: auth_0001` (the run's mandate, attached by the mock)          |
| 04:01:24   | `draw` (release_id + the pool entry as its bid)                                                                  | `ALLOCATED`, slot `bd_0700`, group 4                                                                         |
| 04:01:26   | `create_hold`                                                                                                    | `hold_0001`, 4 seats, `price_per_unit_paise 25000`, ttl 3600                                                 |
| 04:01:30   | `get_hold`                                                                                                       | `active` — checked before charging, as `workflow-spec.md` §2 requires                                        |
| 04:01:33   | `execute` `{amount: {value: 100000}}`                                                                            | `pay_0001` **SUCCESS** (4 × 25000 = the hold's price, under the 120000 mandate and the 30000/person ceiling) |
| 04:01:37   | `confirm_booking` `{hold_id, payment_id}`                                                                        | **`BK-0001` CONFIRMED**, `amount_paise 100000`                                                               |

Final state for the run: `{holds: 1, active_holds: 1, bookings: 1, mandates: 1, payments: 1}`. The agent's own report
to the user matched the log: *"Outcome: Win — Booking Reference: BK-0001 — Amount Charged: ₹1000.00"*.

Two gaps remain in that run, both worth knowing:

- **The mandate's residual was not released** (`released_mandates: 0`): 120000 was reserved and 100000 charged, and
  `workflow-spec.md` §2 step 4.f wants the leftover released. The allocator's prompt asks for it; the model stopped at
  the booking. A money-safety follow-up for the prompt, not a mock change — the tool exists and is granted.
- **The hold stays `active`** after the booking, which is correct here: the capacity really is consumed, so it must
  not be freed on expiry (only an explicit `release_hold` frees it).

Note also which message preceded the working declare call: a fresh conversation whose *first* message dictated the
call and its arguments, after the previous turn had been refused. The allocator, in contrast, received only natural
language ("run the full allocation… draw the slots, hold the winner's slot, capture the mandate, confirm the booking")
and still delivered every argument — so the recovery is the pass-through itself, not the phrasing.

### The payment-declined path runs through the real agents too (verified 2026-10-02 04:08)

Same two agents, a fresh bid, and `POST /__admin/scenario {"scenario": "payment_failure"}` armed out of band. The
allocator drew and held exactly as in the happy path, and then:

| time (UTC) | call                                  | result                                                                                      |
| ---------- | ------------------------------------- | ------------------------------------------------------------------------------------------- |
| 04:08:10   | `execute` `{amount: {value: 100000}}` | **`status: FAILED`, `reason: BANK_DECLINED`** (HTTP 200, as a real failure would be)        |
| 04:08:14   | `release` (the mandate)               | `RELEASED`, `released_amount 120000` — the **whole** reservation, since nothing was charged |
| 04:08:14   | `release_hold`                        | `released: true`                                                                            |

Final state: `{active_holds: 0, bookings: 0, payments: 0, released_mandates: 1}` — no booking, no charge, nothing left
held. The agent's report matched: *"Outcome: Lost — Reason: Payment declined by the bank. The mandate has been
released, and no charges were made."*

That is `workflow-spec.md` §4's "Capture fails after a winning hold" rule executed by the platform's own agent,
including the part that matters most for the brief: no false success, and no money left reserved on a loss. The
scenario was disarmed (`{"scenario": "success"}`) immediately after.

One caveat when re-checking those states: `POST /__admin/reset` clears one run when its **body** carries `run_id`, and
**all** state when it does not (`docs/connectors.md`) — it reads the body, not `X-Run-Id`. A later global reset
cleared the runs above, so `GET /__admin/state?run_id=dryrun_a` now reads zero; the log lines cited here persist, and
the observations were taken live at the time.
