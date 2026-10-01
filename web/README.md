# KIRRO web

Next.js (App Router) front end for KIRRO: a public landing page, a web alternative to the voice declare flow, and an
auth-gated dashboard over KIRRO Core's read endpoints. Deployed separately from KIRRO Core (Vercel); talks to it
over HTTPS, server-side only.

See `../AGENTS.md` → "Web interface" for the contract this app has with KIRRO Core (which endpoints exist, what the
dashboard may and may not do).

## Routes

- `/` — static landing page.
- `/declare` — submits the user's own words as `evidence`, same as the voice flow would; code (KIRRO Core) does all
  parsing, ambiguity handling, and the read-back.
- `/dashboard` — gated by Google OAuth (any Google account; see "Auth" below). Lists declarations, their decision
  log, and persisted eval-run artifacts, all read from KIRRO Core.

## Setup

```
cp example.env .env.local   # fill in KIRRO_API_URL, AUTH_*
pnpm install
pnpm dev
```

`KIRRO_API_URL` must point at a running KIRRO Core (`../scripts/dev.sh` runs one on `:8080` locally). It is a
server-only env var — never exposed to the browser; every KIRRO Core call goes through a Server Component, Route
Handler, or Server Action (`src/lib/kirro.ts`).

## Commands

Same as any app built on `next-frontend-template` — see `AGENTS.md` in this folder for the full convention set
(directory structure, TanStack Query, Zustand, forms, testing). In short: `pnpm dev|build|lint|type-check|test`.

## Auth

Google OAuth via Auth.js v5 (`src/auth.ts`). No allowlist: the dashboard is read-only (no mutation endpoint exists
anywhere in it), so sign-in exists only to keep it off anonymous/bot traffic, not to restrict which people may view
it — any Google account that signs in is let through. If a future view adds a risky action, gate that action
specifically rather than reintroducing a blanket allowlist here. `src/proxy.ts` (Next 16's `middleware.ts`
successor) redirects unauthenticated requests to `/dashboard/*` to Google sign-in.
