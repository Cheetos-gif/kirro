# Web portal — implementation plan

Companion to `docs/decisions/ADR-015-web-portal-for-organisers-users-and-stats.md`. That ADR is the what/why; this
is the how. **Implemented** — `mock_server` (§1–§2) and `web/` (§0, §3–§4) are built; see the ADR's status note for
the two amendments made beyond this plan (per-user `/__admin/state` view, `GET /venue/organisers`).

## 0. Starting point

`next-frontend-plus-template` (vendored to `~/Downloads/next-frontend-plus-template-main` this session,
de-branded — CodeChef-VIT references stripped from `README.md`/`CODE_OF_CONDUCT.md`/`contributing.md`; `LICENSE`'s
original copyright line kept as-is, MIT requires it). Copy into this repo's new `web/` directory as the base; do
not build on the fork's stale `web/`.

From the fork's existing `web/` (`upayanmazumder/kirro`), reusable as-is: `src/auth.ts` (Auth.js + Google, needs a
role lookup added — see §3), `src/api/` (axios client, error normalisation, typed `request<S>()`), `src/lib/query.ts`,
`src/stores/` (Zustand setup), `src/components/ui/` and `src/components/providers/`, the whole test/lint/commit
toolchain. Not reusable: `src/lib/kirro.ts` and everything under `src/schemas/` that models "KIRRO Core" shapes
(declarations/decision-log/eval-runs) — these describe a backend that no longer exists and get replaced wholesale
per §2.

## 1. Data model additions to `mock_server`

New SQLite-backed document kinds (`mock_server/state.py`'s `RunState`, alongside the existing `holds`/`bookings`/
`mandates`/`payments`/`shipments`/`declarations`):

- **`organisers`**: `{organiser_id, name, contact, status: "pending" | "approved", requested_by}` — `requested_by`
  is the web app's user identity (an email, from Google OAuth), not a KIRRO-side concept; the mock just stores it.
- **`events`**: replaces reading straight from `catalogue.json["events"]` at runtime. Same shape as today's fixture
  entries (`event_id, name, aliases, generic_aliases, fulfilment`) plus `organiser_id` and `status: "draft" | "published"`. `catalogue.json`'s existing four events become the seed data loaded into this table on a fresh run,
  not a parallel read path — `find_release`/`list_releases`/etc. in `mock_server/app.py` move from reading
  `st.catalogue["releases"]` to reading this table.
- **`releases`**: same move — `catalogue.json`'s release/slot shape, persisted and mutable, gains `allocation_mode: "fair_draw" | "instant_buy"`.

`load_catalogue()` stays for the pincode table (unrelated, no reason to move) and as the seed-data source for a
fresh run's `events`/`releases`.

## 2. New `mock_server` routes

- `POST /venue/organisers` — self-serve request, `status: "pending"`.
- `POST /venue/organisers/{id}/approve` — admin-only in spirit (no new auth layer in the mock itself — same trust
  model as `/__admin/*` today: the web app's own admin-role check gates who can call this, the mock just executes
  it).
- `POST /venue/events` / `PATCH /venue/events/{id}` — organiser creates/edits an event, scoped to their
  `organiser_id`.
- `POST /venue/releases` — organiser creates a release (slots, prices, `allocation_mode`) under one of their events.
- `POST /venue/releases/{id}/buy` — **new**, `instant_buy` only. One call: checks capacity, creates the hold,
  captures payment, confirms the booking — no `declare_interest`, no `allocator.draw`. Rejected (409) if the
  release's `allocation_mode` is `fair_draw` — that path still only goes through the existing declare → draw →
  hold → capture chain, unchanged, enforced server-side so the web app can't accidentally bypass the fairness
  mechanic by calling the wrong endpoint.
- Admin stats: no new endpoint planned by default — the web app's server components compute totals (events,
  organisers, users, declared-interest counts, draw outcomes, revenue captured vs. released) from the existing
  list/read endpoints. Revisit if that turns out to be too many round trips for the admin page to load acceptably.

Each of these goes through the existing `serve(request, target, handler)` wrapper (scenarios, idempotency, request
logging) per the "how to add a mock route" convention in `AGENTS.md` — no new pattern invented.

## 3. Roles and auth

Extends the fork's existing Auth.js/Google setup, not a replacement. On sign-in, look up the user's role:

- Default: **user**. No approval needed — matches the fork's existing "any Google account passes" posture.
- **Organiser**: self-serve request (`POST /venue/organisers`) from a signed-in user, `status: "pending"` until an
  admin approves it. Until approved, the requester is still a plain user.
- **Admin**: not self-serve — a small seeded allowlist (emails), checked in `src/auth.ts` alongside the Google
  provider, not stored in the mock (the mock has no concept of "admin" at all; it just executes whatever the
  already-authorized caller sends, same trust boundary as `/__admin/*` today).

## 4. Page plan

| Route                | Role      | Replaces (fork) | Notes                                                                                                                                                             |
| -------------------- | --------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                  | public    | landing page    | Event listings: organiser, price, capacity, `fair_draw`/`instant_buy` badge                                                                                       |
| `/events/[id]`       | public    | — (new)         | Detail; `instant_buy` → buy button → `/venue/releases/{id}/buy`; `fair_draw` → declare-interest form scoped to this event, replacing the old free-text `/declare` |
| `/dashboard`         | user      | `dashboard/*`   | My declarations, draw outcomes, payment history, confirmed bookings — all re-pointed at `mock_server`, not "KIRRO Core"                                           |
| `/organiser`         | organiser | — (new)         | Create/edit my events and releases; applicant counts and allocation outcomes per release I own                                                                    |
| `/organiser/request` | user      | — (new)         | The self-serve organiser-status request form                                                                                                                      |
| `/admin`             | admin     | — (new)         | Cross-cutting stats, all organisers/users/events, pending organiser approvals, scenario controls for live demo runs                                               |

## 5. What this explicitly does not change

- The AgenticOrg agent's own flow (declare → pool → draw → hold → capture → confirm, `agent-spec.md`/
  `workflow-spec.md`) is untouched. The web portal is a second caller of the same mock, not a replacement for the
  phone/WhatsApp declared-interest channel — someone can still declare interest by talking to the agent; the portal
  is an additional, visual way to do the same thing, plus the parts (organiser side, admin stats, instant-buy) that
  have no voice/chat equivalent at all.
- `instant_buy` never touches `allocator/engine.py` — intentionally a separate, simpler path, not a variant of the
  fair-draw algorithm.

## 6. Phasing (suggested, not yet sequenced into a todo)

1. Vendor the template into `web/`, wire env/auth, confirm it builds and deploys with zero KIRRO-specific code yet.
1. `mock_server`: move events/releases into the store (§1), with the existing fixture as seed data — verify every
   existing test still passes unchanged (this step alone should be behaviour-neutral).
1. `mock_server`: new routes (§2) plus their test coverage.
1. Web app: public listing + event detail + instant-buy flow (the shortest path to something demoable).
1. Web app: dashboard (user), re-pointed at the new data.
1. Web app: organiser flow (request, create event/release, view outcomes).
1. Web app: admin flow (approvals, stats, scenario controls).
