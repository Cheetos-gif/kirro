# KIRRO on AgenticOrg — implementation spec

Plan: `docs/decisions/ADR-010-agenticorg-platform-vachana-mock-budget.md` (connector facts) and
`docs/decisions/ADR-011-kirro-brain-moves-to-agenticorg.md` (architecture, file disposition, risks, dependency
order). Read both before touching any file in this directory or implementing against it.

These are **planning artifacts**, written before implementation (2026-10-02). Nothing here has been built or
registered on the live platform yet. Items marked `[INFERENCE]` or "unverified" were not confirmed live — verify
before relying on them (ADR-011 §8 step 1).

- `agent-spec.md` — the "Kirro Declare" conversational Virtual Employee: Persona, Role, Prompt (verbatim,
  copy-pasteable), Behavior rules, Authorized Tools, tool invocation contracts, failure handling, memory/state.
- `workflow-spec.md` — the "Kirro Window Allocation" Workflow: trigger, steps, idempotency, notification templates.
- `setup-runbook.md` — connector registration (exact field values), environment/secrets, demo steps.
- `evals.md` — eval cases written against the live platform agent (the E01–E10 local-oracle suite they were
  cross-referenced against was removed with the migration; its inputs survive as history in `docs/evals.md`).

Source-of-truth extraction this spec is built from: the pre-migration local oracle (`agent/state/machine.py`,
`agent/state/fields.py`, `agent/policies/*`, `agent/core.py`, `agent/tools/*`, `agent/system-prompt/v0.md`,
`connectors/*`, `evals/cases/*.yaml`). That code was **removed** from the repo with the AgenticOrg migration —
issue #1 overrides ADR-011 §3's "keep as an oracle", so this directory, with `allocator/*` and `mock_server/*`, is
the only surviving record of those rules.
