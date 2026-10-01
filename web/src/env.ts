import { createEnv } from '@t3-oss/env-nextjs';
import * as z from 'zod';

export const env = createEnv({
  server: {
    // Internal KIRRO Core base URL. Never exposed to the browser: all declare-flow and
    // dashboard reads go through Next.js Route Handlers / Server Actions, which proxy here.
    KIRRO_API_URL: z.url(),
    AUTH_SECRET: z.string().min(1),
    AUTH_GOOGLE_ID: z.string().min(1),
    AUTH_GOOGLE_SECRET: z.string().min(1),
  },
  experimental__runtimeEnv: {
    KIRRO_API_URL: process.env.KIRRO_API_URL,
    AUTH_SECRET: process.env.AUTH_SECRET,
    AUTH_GOOGLE_ID: process.env.AUTH_GOOGLE_ID,
    AUTH_GOOGLE_SECRET: process.env.AUTH_GOOGLE_SECRET,
  },
  emptyStringAsUndefined: true,
  skipValidation: !!process.env.SKIP_ENV_VALIDATION,
});
