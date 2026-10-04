import { NextResponse } from 'next/server';

import { auth } from '@/auth';
import { env } from '@/env';

export const dynamic = 'force-dynamic';

/**
 * The VAPID public key is not secret (the browser's own `pushManager.subscribe` call needs it as
 * `applicationServerKey`) but is still not `NEXT_PUBLIC_*`, to keep every env var in `env.ts`
 * server-only per that file's own convention. Served from a signed-in-only route instead — a
 * bare key by itself cannot subscribe or send anything, but there is no reason to answer it to an
 * anonymous caller either.
 */
export async function GET() {
  const session = await auth();
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Sign in first.' }, { status: 401 });
  }
  if (!env.VAPID_PUBLIC_KEY) {
    return NextResponse.json({ error: 'Push notifications are not configured.' }, { status: 503 });
  }
  return NextResponse.json({ publicKey: env.VAPID_PUBLIC_KEY });
}
