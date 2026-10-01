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

## 4. Tenant state observed (2026-10-02)

**Connectors — 7, all active.** `whatsapp_kirro` (comms, `meta_business`, 5 tools: `get_business_profile`,
`get_message_templates`, `send_media_message`, `send_template_message`, `send_text_message`), `tally` (finance,
bridge, 3), `zoho_books` (finance, oauth2, 4), `gstn` (finance, api_key, 4), `banking_aa` (finance, oauth2, 2),
`stripe` (finance, api_key, 2), `pinelabs_plural` (finance, api_key, 2 — ADR-010 listed six tools for this
connector, so re-check when wiring the charge leg).

Not yet registered but present in the registry: **`agent_scheduler`** (`schedule_agent_task`, `cancel_agent_task`,
`list_my_schedules`, `cancel_merchant_schedules` — the Workflow trigger needs this) and `twilio`.

**Agents — 5, all shadow/untouched:** Vendor Manager, Support Triage, Compliance Guard, It Operations, Contract
Intelligence. No active agents, no workflows configured yet, 0 pending approvals.

## 5. Not yet inspected (do not assume)

- The Agent creation wizard's Role/Prompt/Behavior/Review steps (ADR-011 §8.1 step 1) — and therefore the exact
  shape of the **Authorized Tools** checklist (dot vs `__` identifiers, per ADR-011 Risk 2).
- The Workflow builder: whether a Workflow step can call native connectors directly or message a user
  (ADR-011 Risk 4), and how the Agent Scheduler trigger is wired.
- Whether a **non-MCP** connector yields callable operations (Risk 2) — the mocks will use MCP, but Vachana has no
  valid non-`mcp` prefix, so this decides whether Vachana needs an MCP shim in front of it.
- Audit Log / Observatory export specifics for Q1.2 (ADR-011 §7.6).
