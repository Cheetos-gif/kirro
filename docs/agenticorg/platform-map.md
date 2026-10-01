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
