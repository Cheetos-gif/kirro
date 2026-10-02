# KIRRO web portal

The human-facing portal for KIRRO: public listings, the declared-interest and instant-buy flows, a user
dashboard, an organiser surface, and an admin surface with live-demo scenario controls. It is a **second caller**
of `mock_server` — the AgenticOrg agent is the other — and never the decision-maker. See
`docs/decisions/ADR-015-web-portal-for-organisers-users-and-stats.md` and `docs/web-portal/plan.md`.

Built from `next-frontend-plus-template` (vendored, de-branded). The mock server itself lives at the repo root;
this directory is deployed separately.

## Roles

Over one Google OAuth (Auth.js v5). Role is resolved per request in `src/lib/auth/roles.ts`, not baked into the
session, so an approval after sign-in takes effect without re-login:

- **user** — default; any Google account.
- **organiser** — self-serve request (`/organiser/request`), approved by an admin. Until approved the requester
  stays a plain user. Resolution reads `mock_server`'s organisers for an approved `requested_by` matching the email.
- **admin** — the `ADMIN_EMAILS` allowlist in env, never stored in the mock.

## Talking to the mock

Everything is **server-side** (Next server components and server actions); nothing about the mock is exposed to
the browser. `src/api/` (axios client, error normalisation, typed `request()`) aims at `MOCK_API_URL` and attaches
the mock's `X-Run-Id` correlation header. `src/lib/kirro/` holds the zod schemas and typed calls for the mock's
real shapes (`src/lib/kirro/schemas.ts`, `src/lib/kirro/api.ts`).

`src/app/actions.ts` holds the server actions. The instant-buy action creates the mandate and calls
`/venue/releases/{id}/buy`; the declare action reserves the mandate and adds the bid to the pool. **A fair-draw
release cannot be bought through the portal** — the mock refuses `/buy` for it with 409 server-side, and the UI
only ever renders the declare form for that mode.

## Environment

Copy `example.env` to `.env.local` (git-ignored) and fill it in — see that file for each variable. Summary:
`MOCK_API_URL`, `MOCK_RUN_ID`, `ADMIN_EMAILS`, `AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`.

## Running

```bash
# from the repo root, in one terminal:
bash scripts/dev.sh            # mock server on :8081

# here:
pnpm install
pnpm dev                       # http://localhost:3000
```

Checks:

```bash
pnpm type-check
pnpm lint
pnpm test
pnpm build
```

## Deploying

Vercel, from the fork (`upayanmazumder/kirro`). Set the env vars above on the Vercel project; point
`MOCK_API_URL` at the deployed mock (`https://api-kirro.upayan.dev`) and set `AUTH_TRUST_HOST=true`. Google OAuth
needs the deployed callback URL registered: `https://<domain>/api/auth/callback/google`.

## Layout

- `src/app/` — routes: `/`, `/events/[id]`, `/dashboard`, `/organiser`, `/organiser/request`, `/admin`, `/signin`.
- `src/app/actions.ts` — server actions (declare, buy, organiser request, event/release creation, approvals,
  scenario control, reset).
- `src/lib/kirro/` — mock schemas, typed API calls, formatters.
- `src/lib/auth/roles.ts` — viewer + role resolution and route guards.
- `src/components/` — shadcn/Base UI components (`ui/`), site header, auth buttons.
