import { AccessToken } from 'livekit-server-sdk';
import { NextResponse } from 'next/server';

import { auth } from '@/auth';
import { env } from '@/env';

export const dynamic = 'force-dynamic';

/** Room names are per-viewer so two callers never share a room (and so the worker's captions are not mixed). */
function roomName(email: string): string {
  return `kirro-${email.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
}

/**
 * Mint a LiveKit access token for the signed-in viewer.
 *
 * The agent worker joins whichever room a participant is in, so the token is the only thing that
 * lets a browser reach the voice agent. Signed here, with the LiveKit key pair, which never reaches
 * the browser (ADR-017).
 */
export async function POST() {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) {
    return NextResponse.json({ error: 'Sign in to talk to KIRRO.' }, { status: 401 });
  }
  if (!env.LIVEKIT_API_KEY || !env.LIVEKIT_API_SECRET) {
    return NextResponse.json({ error: 'Voice is not configured.' }, { status: 503 });
  }

  const token = new AccessToken(env.LIVEKIT_API_KEY, env.LIVEKIT_API_SECRET, {
    identity: email,
    name: session?.user?.name ?? undefined,
    ttl: '15m',
  });
  token.addGrant({
    room: roomName(email),
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    // Subtitles and voice-agent captions arrive over the data channel.
    canPublishData: true,
  });

  return NextResponse.json({ token: await token.toJwt(), room: roomName(email) });
}
