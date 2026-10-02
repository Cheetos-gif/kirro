# ADR-015: A web portal for organisers, users, and stats — planning only

Status: accepted (2026-10-02) — **planning only, not yet implemented.** Code changes described here are future
work; this ADR and `docs/web-portal/*` are the implementation spec for that work, mirroring how ADR-011 and
`docs/agenticorg/*` work together.

## Context

AgenticOrg's own dashboard shows agent/workflow/connector management — the tech-ops view of KIRRO as a Virtual
Employee. It shows none of KIRRO's actual domain: which events exist, who organises them, who declared interest,
what a draw produced, what got paid and refunded. For a judge-facing demo, that domain state currently only exists
as raw JSON behind `mock_server`'s REST/MCP routes and the AgenticOrg chat transcript — there is no human-readable
storefront, no organiser view, no admin stats view, no user-facing payment/application history.

A `web/` Next.js app already exists in a fork of this repo (`upayanmazumder/kirro`), built from
`next-frontend-plus-template`. Its infrastructure (Google OAuth via Auth.js, TanStack Query, typed API client
layer, test/lint toolchain) is sound and reusable. Its domain code is not: it targets `KIRRO_API_URL` → "KIRRO
Core", the FastAPI brain ADR-011 deleted (`/declare` submitting free-text `evidence`, a dashboard reading a
decision log and eval-run artifacts that no longer exist). None of that backend exists anymore.

## Decision

1. A new `web/` app lives in **this repo** (`Cheetos-gif/kirro`), built from the same template
   (`next-frontend-plus-template`, vendored and de-branded — see `docs/web-portal/plan.md` §0), not a revival of the
   fork's stale one. Deployed separately (Vercel), talks to `mock_server` over HTTPS, server-side only — same
   separation-of-concerns the fork already established.
1. Three roles — **user**, **organiser**, **admin** — over the same Google OAuth. Organiser status is **self-serve**:
   any signed-in user may request it; requests need an approval step (admin-side), not instant grant. Full model in
   `docs/web-portal/plan.md` §3.
1. Events move from `mock_server`'s static `catalogue.json` fixture to the SQLite-backed store, gaining an
   `organiser_id` and an `allocation_mode` of `fair_draw` (today's full declare → draw → hold → capture chain,
   ADR-002's fairness mechanic, unchanged) or `instant_buy` (a new, shorter hold → capture chain with **no draw
   step at all** — literal first-come, by design, for non-scarce listings). Full data model and new mock routes in
   `docs/web-portal/plan.md` §1–§2.
1. Page plan, phasing, and what's reused vs. rewritten from the fork's existing `web/`: `docs/web-portal/plan.md`
   §4–§6.

## Consequences

- **ADR-002 is not weakened.** `fair_draw` events keep the exact mechanism (seeded weighted permutation, capacity
  checked at assignment, speed buys nothing). Putting `instant_buy` in the same product, visibly, is a feature for
  the submission's narrative: it makes the contrast between naive first-come allocation and KIRRO's fair draw
  demonstrable side by side, not just asserted.
- `mock_server` gains real write surface it didn't have before (organiser-created, mutable events) — still a mock,
  still single-writer SQLite per ADR-013, still never a decision-maker; the web app and the AgenticOrg agent are
  both callers of it, not of each other.
- A second top-level service (`web/`, deployed to Vercel) — the thing AGENTS.md's "no new top-level services
  without an ADR" rule exists to gate. This ADR is that gate.
- The fork's existing `web/` (`upayanmazumder/kirro`) is superseded, not built on top of; its page shells
  (`dashboard/eval-runs.tsx`, `check-name.tsx`, the `/declare` free-text flow) do not carry forward — they're
  artifacts of the pre-ADR-011 architecture.

## Open questions

- Whether admin-side organiser approval is a real workflow (queue, notify) or, for the demo, just a flag an admin
  flips directly — leaning toward the latter given the scale this needs to work at, not yet decided.
- Whether `instant_buy` events need their own scenario-table coverage in `mock_server` (timeout/malformed/etc., like
  the `fair_draw` chain has) or whether reusing the existing scenario machinery on the new route is sufficient —
  likely the latter, not yet verified.
