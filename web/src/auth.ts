import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';

/**
 * Auth.js v5 with Google OAuth. Any Google account may sign in (the default `user` role); organiser and admin
 * roles are derived from mock state and the admin email allowlist at request time (see `@/lib/auth/roles`), not
 * baked into the session, so an approval made after sign-in takes effect without re-login.
 */
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  trustHost: true,
  session: { strategy: 'jwt' },
  pages: { signIn: '/' },
});
