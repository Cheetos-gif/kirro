import { createEnv } from '@t3-oss/env-nextjs';
import * as z from 'zod';

/**
 * Server-only environment. The portal talks to `mock_server` server-side (Vercel functions), never from the
 * browser, so nothing here is `NEXT_PUBLIC_`. Auth.js reads AUTH_SECRET / AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET
 * from the environment itself; they are declared here so a missing value fails loudly at startup.
 */
export const env = createEnv({
  server: {
    MOCK_API_URL: z.url().default('http://127.0.0.1:8081'),
    // Which mock run the portal reads and writes. Default shares the AgenticOrg agent's run.
    MOCK_RUN_ID: z.string().min(1).default('default'),
    // The voice bridge's LiveKit room (ADR-017). `LIVEKIT_URL` is the WebSocket the browser
    // connects to, handed to the client component as a prop; the key pair signs access tokens
    // server-side and never leaves the server.
    LIVEKIT_URL: z.string().default('ws://127.0.0.1:7880'),
    LIVEKIT_API_KEY: z.string().default(''),
    LIVEKIT_API_SECRET: z.string().default(''),
    // Comma-separated Google emails granted the admin role. Not stored in the mock.
    ADMIN_EMAILS: z.string().default(''),
    AUTH_SECRET: z.string().min(1).optional(),
    AUTH_GOOGLE_ID: z.string().min(1).optional(),
    AUTH_GOOGLE_SECRET: z.string().min(1).optional(),
    AUTH_TRUST_HOST: z.string().optional(),
  },
  client: {},
  experimental__runtimeEnv: {},
  emptyStringAsUndefined: true,
  skipValidation: !!process.env.SKIP_ENV_VALIDATION,
});

export function adminEmails(): string[] {
  return env.ADMIN_EMAILS.split(',')
    .map(email => email.trim().toLowerCase())
    .filter(Boolean);
}
