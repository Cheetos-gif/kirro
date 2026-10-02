# ADR-014: Q1.2 evidence comes from the platform's audit surfaces, cross-referenced with the mock's request log

Status: accepted (2026-10-02)

## Context

ADR-011 §7.6 left this open: whether KIRRO's own decision log duplicates, or must feed, the platform's native Audit
Log / Observatory / Enforce Audit pages for Q1.2 reconstruction. Issue #1 then deleted the repo-side decision log
(`logging_/decision_log.py`, `logging_/reconstruct.py`) and `scripts/reconstruct.sh`, because the platform decides and
acts — the repo no longer sits on the decision path, so it also no longer sees the decisions.

What exists now, verified live on 2026-10-02:

- **The platform's Audit Log** (`GET /api/v1/audit`, and the Audit Log page) records structured governance events —
  `agent.run`, `hitl.decided`, `agent.create`/`agent.deleted`,
  `agent.governance_change.requested|approved|applied` — with actor, actor type, resource, action, outcome, details
  and timestamp. Two gaps were observed directly: our simulated Window Allocation run produced **no events at all**,
  and tool arguments are never included.
- **Approvals** (`GET /api/v1/approvals`) is the richest agent-side record. Each row carries the user's query, the
  agent's exact `raw_output`, `confidence`, `trigger`, `thread_id`, the `tool_calls` list (tool name and a success
  status), and the `resume_config` the turn ran with (model, provider, connector ids, authorised tools, the prompt's
  SHA-256, the confidence floor) — plus the human decision, who made it and when.
- **The mock's per-run JSONL** records every REST request and, since this session, every MCP tool invocation with the
  arguments as received, alongside the scenario, response, status and latency, keyed by `X-Run-Id`.
- The two disagree in a way that matters: a tool call can read `status: success` in the approvals record while our
  handler returned a refusal, because the platform records that the call completed, not what it decided.

## Decision

1. Q1.2 is reconstructed from the **platform's own records** — the Audit Log and the Approvals trail — because those
   are the artefacts the Virtual Employee actually runs on, and they are the only place the human-in-the-loop decision
   (who approved what, when, on what basis) is captured.
1. The **mock's JSONL is the connector-level witness** cited alongside them. Where they disagree, the mock's log is
   authoritative for what a connector received and returned; the platform's record is authoritative for what the
   agent decided and who approved it.
1. The repo does **not** re-implement a decision log or a reconstruction tool. `logging_/redact.py` stays, so anything
   the mock logs is still scrubbed on write; no new `logging_` module is added.
1. Every row of the submission's Q1.2 table cites one of: an Audit Log event, an approval row, or a mock log line —
   with the run id and timestamp.

## Consequences

- Q1.2 is reproducible by anyone holding a platform account (Audit Log page, Approvals page) plus the mock's log for
  the connector leg; no repo script is needed to regenerate it.
- The mock log becomes load-bearing for the submission, so it must keep recording tool invocations with their
  arguments (added this session) and stay readable per run.
- Gaps to state honestly rather than paper over: the platform's audit log did not record our Workflow run; it never
  records tool arguments; `GET /workflow-runs/{id}` requires OAuth, so run-level detail is visible only in the UI.
- Redaction is now partly outside our control — the platform's records are quoted as they are, and must be reviewed
  before they go in the submission.

## Open questions

- Whether the platform can export Audit Log rows per run for the submission, or whether API reads and screenshots are
  the only route.
- Whether the Workflow's step-level trace becomes visible once a run succeeds; today a run produces no audit events.
