import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';

import { env } from '@/env';

// Dashboard is read-only (no mutation endpoint exists anywhere in it) — the only reason to gate
// it at all is to keep it off anonymous/bot traffic, not to restrict who among people may view
// it. Any signed-in Google account passes. If a future dashboard view ever adds a risky action,
// gate that action specifically rather than widening this file back into an allowlist.
export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [Google({ clientId: env.AUTH_GOOGLE_ID, clientSecret: env.AUTH_GOOGLE_SECRET })],
  secret: env.AUTH_SECRET,
  session: { strategy: 'jwt' },
  pages: { signIn: '/login' },
});
