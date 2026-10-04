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
`MOCK_API_URL`, `MOCK_RUN_ID`, `ADMIN_EMAILS`, `AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`,
`MOCK_ADMIN_KEY` (gates the mock's `/__admin/*` surface; blank is a no-op), `VAPID_PUBLIC_KEY`/
`VAPID_PRIVATE_KEY`/`VAPID_SUBJECT` (Web Push; blank disables push notifications entirely).

## Running

```bash
# from the repo root, in one terminal:
bash scripts/dev.sh            # mock server on :8081

# here:
pnpm install
pnpm dev                       # http://localhost:3000
```

That native flow is the faster one day to day. The alternative is the compose stack from the repo
root (`web/Dockerfile`, ADR-021), which brings the portal _and_ the mock up together with no host
Node install:

```bash
docker compose up --build                            # dev: this directory is bind-mounted, pnpm dev
docker compose -f docker-compose.yml up --build      # prod-like: the standalone `next start` image
```

Compose sets `MOCK_API_URL=http://mock:8081` — from inside the portal's container the mock is another
container, so `127.0.0.1` from `example.env` would be wrong there; `environment` beats `env_file`, so
the override is automatic. `web/.env.local` is read if present and not required if absent (without
`AUTH_GOOGLE_*`, sign-in is simply unavailable). No credential is ever baked into the image: the app
reads its env at runtime, and `web/.dockerignore` keeps `.env*` out of the build context.

`next.config.ts` sets `output: 'standalone'` for that image. Vercel ignores the setting.

Checks:

```bash
pnpm type-check
pnpm lint
pnpm test
pnpm build
```

## Deploying

Vercel project `kirro-web` (Root Directory `web`, Node 24.x), **git-connected to the fork
`upayanmazumder/kirro`** — so a push to that repo's `main` is the deploy. Live at
<https://kirro.upayan.dev>.

Production environment variables: `MOCK_API_URL=https://api-kirro.upayan.dev`, `MOCK_RUN_ID=default`,
`LIVEKIT_URL=wss://voice-kirro.upayan.dev`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (the same key pair
the cluster's `kirro-voice` secret holds — it signs the browser's room tokens),
`ADMIN_EMAILS` (comma-separated), `AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_TRUST_HOST=true`,
`MOCK_ADMIN_KEY` (must match the cluster's `kirro-mock-admin` secret exactly), `VAPID_PUBLIC_KEY`,
`VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (generate a pair with `node -e "console.log(require('web-push').generateVAPIDKeys())"`,
once — rotating it invalidates every existing subscription).
Google OAuth needs the deployed callback URL registered: `https://<domain>/api/auth/callback/google`.

Env changes need a **new deployment** — `vercel redeploy` reuses the source deployment's env snapshot, so push a
commit (or trigger a fresh Git deploy) for the change to take effect.

## Layout

- `src/app/` — routes: `/`, `/events/[id]`, `/dashboard`, `/organiser`, `/organiser/request`, `/admin`,
  `/signin`, `/talk` (the LiveKit voice channel, ADR-017), `/api/voice/token` (mints a room token for
  the signed-in viewer), `manifest.ts` (PWA manifest), and `/api/push/vapid-public-key`.
- `src/app/actions.ts` — server actions (declare, buy, organiser request, event/release creation, approvals,
  scenario control, reset).
- `src/lib/kirro/` — mock schemas, typed API calls, formatters.
- `src/lib/push/` — Web Push: `send.ts` (server-side, VAPID-signed), `subscribe.ts` (client-side
  `pushManager.subscribe`/permission helpers). `public/sw.js` holds the service worker itself
  (install/fetch/push/notificationclick); `src/components/pwa/` registers it.
- `src/lib/auth/roles.ts` — viewer + role resolution and route guards.
- `src/components/` — shadcn/Base UI components (`ui/`), site header, auth buttons.
