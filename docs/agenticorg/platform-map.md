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
Business credentials, which we do not have — flagged to the user. Note the connector page's own `Edit` form cannot
supply them either (its auth-type list has no `meta_business`).

`PATCH /api/v1/agents/{id} {"connector_ids":[…]}` currently returns 503 for every variant tried, including dropping
whatsapp, so the agent's linked set cannot be changed while this is broken.

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
`7b1f072c-1019-434b-af81-1d66e517611b`, domain `ops`, linked to the single aggregate connector `mcp_kirro_all`, with
**10 tools granted in one PATCH (200)**: `draw`, `create_hold`, `get_hold`, `release_hold`, `confirm_booking`,
`execute`, `release`, `refund`, `list_releases`, `list_pool_entries`.

**`Kirro Window Allocation`** — `POST /api/v1/workflows` returned 201, id
`f22042ff-0682-4894-8c9c-cd3d3c835783`, domain `ops`, `trigger_type: manual`, with these steps persisted in
`definition.steps`:

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
