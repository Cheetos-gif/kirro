# syntax=docker/dockerfile:1

# KIRRO web portal image — the local docker-compose build (ADR-021). This is NOT the deploy path:
# the portal is deployed to Vercel from the fork (web/README.md). The image exists so
# `docker compose up` can bring up the portal next to the mock without a host Node install.
#
# Stages: `base` (interpreter + pnpm) -> `deps` (installed node_modules) -> `dev` (what the compose
# override targets) and `builder` -> `runner` (the production-shaped image, `node server.js`).
#
# No credential is ever an ARG or an ENV here. The app reads every variable at runtime, server-side
# (src/env.ts), and the compose file supplies them; baking an AUTH_SECRET into a layer is exactly the
# mistake web/.dockerignore's `.env*` line also guards against.
#
# Node 24 matches the version Vercel builds the portal with (web/README.md).
FROM node:24-slim AS base

# corepack resolves the pinned pnpm from package.json's `packageManager` — the same pin Vercel
# honours — instead of whatever pnpm happens to be on the machine. No prompt in a non-TTY build.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PNPM_HOME=/pnpm \
    PATH="/pnpm:${PATH}" \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

WORKDIR /app

# ------------------------------------------------------------------------------------------------ deps
FROM base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# The store is a BuildKit cache (shared with the dev stage below), so a rebuild after a
# package.json change, or a retry after a flaky registry connection, reuses the tarballs already
# downloaded instead of starting over.
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

# ------------------------------------------------------------------------------------------------ dev
# Targeted by docker-compose.override.yml: the checked-out source is bind-mounted over /app, so this
# stage only has to supply pnpm and a container-built node_modules. It reuses the deps stage's
# install rather than resolving the lock a second time — same lock, same result, half the work.
FROM base AS dev

ENV NODE_ENV=development

COPY --from=deps /app/node_modules ./node_modules
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

EXPOSE 3000
# --hostname 0.0.0.0 so the port is reachable from outside the container; Next's dev server is
# otherwise free to pick its own default.
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]

# ------------------------------------------------------------------------------------------------ build
FROM base AS builder

COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `next build`, no secrets present. next.config.ts sets output: 'standalone', so the product is
# .next/standalone (server.js + the traced node_modules), .next/static and public.
RUN pnpm build

# ------------------------------------------------------------------------------------------------ runtime
FROM base AS runner

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root runtime, same uid convention as the mock image.
RUN groupadd --system --gid 10001 nodejs \
    && useradd --system --uid 10001 --gid nodejs --create-home nextjs

# The standalone bundle carries its own node_modules (only the traced dependencies) and server.js;
# .next/static and public are served by that server but are not traced into it, so they are copied
# explicitly. Nothing else from the build stage is needed — not pnpm, not the full node_modules.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
