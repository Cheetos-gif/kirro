# ADR-020: a scheduled sync mirrors AgenticOrg's agent stats into the mock, for the portal to display

Status: accepted (2026-10-04)

## Context

The portal's homepage and README make claims about how well the agent performs. Those claims have so
far been either hand-written prose or absent: the real numbers — accuracy, how many turns have been
scored, whether an agent is `active` or `shadow` — exist **only** on AgenticOrg, on each agent's
record (`docs/agenticorg/platform-map.md` §10, §11; `docs/agenticorg/declare-v6-notes.md` §7). A reader
of the site has no way to tell a verified number from a hopeful sentence.

Reading those numbers from here is possible but awkward, for a reason already documented: API keys on
AgenticOrg are `agenticorg:admin`-only (`/api/v1/org/api-keys` → `403 Missing scope`,
`platform-map.md` §13), and that access is not available. The one reachable path is the same one
`voice_bridge` and `allocator_bridge` already use: sign in with the account's own email and password,
hold the cookie session, and call the platform's own JSON API — `GET /api/v1/agents/{id}` for the
record, in this case, rather than `POST /api/v1/chat/query` for a turn.

Two things make this worth a small scheduled job rather than a one-off copy: the numbers change as the
demo runs, and the portal must never imply a stale number is live.

## Decision

A second small, stateless script — `agent_stats_sync/` — runs on a Kubernetes CronJob (every 5
minutes) and, once per pass, for each configured agent id:

1. `GET /api/v1/agents/{id}` over the existing cookie session (reusing
   `voice_bridge.agenticorg.AgentChat`, which gains a `get_json` method for a plain authenticated read
   — one login/CSRF implementation, not two).
1. Keeps only the fields a stat card should show (`name`, `status`, `accuracy`,
   `shadow_accuracy_current`, `shadow_sample_count`, `shadow_min_samples`, `shadow_accuracy_floor`),
   stamps `synced_at`, and `PUT`s the result to the mock.

`mock_server` stores each snapshot verbatim in a new `agent_stats` table (the same `PTable` shape as
`users`/`declarations`, ADR-013 — no new database), keyed by agent id, and exposes it on two routes:

- `PUT /__admin/agent-stats/{agent_id}` — admin-key gated, same as every other `/__admin/*` route
  (`#22`); this is sync-job harness state, not something reached in normal use.
- `GET /venue/agent-stats` — **public**, because the point of this ADR is to put the numbers in front
  of a reader. It answers `{"agents": []}` before the first sync, which the portal renders as nothing
  at all.

**The mock validates the envelope, never the numbers.** It does not know which fields AgenticOrg
exposes, so it must not invent, coerce or drop them; a field the platform stops returning simply goes
absent, and the portal renders "—" rather than a zero. "Not measured" and "measured as zero" are
different claims.

**This is a mirror, not a source of truth, and it writes nothing back.** No number here changes any
decision, and the mock remains the only thing the booking path trusts. It is also why plain accuracy
figures shown on a public page are acceptable: they describe a model's scoring on a demo tenant, not
user data.

**Failure is per-agent and non-destructive.** One agent's unreadable record is logged and skipped
rather than failing the pass; a failed pass leaves the previous snapshot in place. That staleness is
made visible in the UI by `synced_at`, always rendered next to the number — the alternative (quietly
showing an old number as current) is the failure mode this ADR is most concerned to avoid.

## Consequences

- New top-level package `agent_stats_sync/` (config, extract/store logic, a `python -m` entrypoint) and
  a new `k8s/agent-stats-sync-cronjob.yaml` — another exception to "no new top-level services" granted
  on the same basis ADR-016/017/018 granted theirs: a read-only mirror of state that already exists
  elsewhere, not a second decision-maker. The existing `kirro-mock-ingress` NetworkPolicy already
  admits any pod in the namespace to the mock's port, so no policy change is needed.
- `mock_server/state.py`: one new `PTable`; `mock_server/app.py`: two new routes.
- `voice_bridge/agenticorg.py`: a `get_json(path)` method, reusing its login, session and CSRF
  handling. The package name is already a known inaccuracy for this kind of reuse (noted in ADR-018);
  this widens it rather than repeating the logic.
- Runs against the credentials already in the `kirro-voice` Secret and the admin key already in
  `kirro-mock-admin` — no new secret.
- Syncs only the ids configured in `AGENT_STATS_AGENT_IDS` (default: Kirro Declare v6, Kirro
  Allocator). Adding, retiring or re-promoting an agent needs that list updated; a stale id is logged
  and skipped, not fatal.
- Does **not** write an audit trail of its own: the numbers are a display mirror, and the platform's
  own Audit Log remains the record of what the agents did (`ADR-014`).
