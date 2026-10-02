'use client';

import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
  useTranscriptions,
  useVoiceAssistant,
} from '@livekit/components-react';
import '@livekit/components-styles';
import { ConnectionState } from 'livekit-client';
import { useCallback, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const STATE_LABEL: Record<string, string> = {
  initializing: 'Connecting…',
  idle: 'Listening',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
};

/**
 * The live call: LiveKit carries the audio, the agent worker on the other side runs Gnani speech and
 * the AgenticOrg agent (ADR-017). This component owns nothing but the connection and the captions.
 */
function Call() {
  const { state, audioTrack } = useVoiceAssistant();
  const connection = useConnectionState();
  const transcriptions = useTranscriptions();
  const { localParticipant } = useLocalParticipant();

  const label =
    connection === ConnectionState.Connected
      ? (STATE_LABEL[state] ?? state)
      : connection === ConnectionState.Connecting
        ? 'Connecting…'
        : 'Not connected';

  return (
    <div className="flex flex-col gap-4">
      <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
        {label}
      </span>

      {/* LiveKit's own visualiser, driven by the agent's audio track. */}
      <BarVisualizer
        state={state}
        trackRef={audioTrack}
        barCount={44}
        className="h-24 w-full rounded-2xl border border-border bg-muted/20 px-4 [--lk-fg:var(--primary)]"
      />

      <div className="max-h-80 min-h-24 overflow-y-auto rounded-2xl border border-border p-4">
        {transcriptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing yet. Say what you want to book — the event, the date, your group size, and the
            most you will pay per person.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {transcriptions.map((line, index) => {
              const mine = line.participantInfo.identity === localParticipant.identity;
              return (
                <li key={index} className="text-sm">
                  <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
                    {mine ? 'You' : 'KIRRO'}
                  </span>
                  <p className={mine ? 'text-muted-foreground' : 'text-foreground'}>{line.text}</p>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export function TalkClient({ serverUrl }: { serverUrl: string }) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  const start = useCallback(async () => {
    setConnecting(true);
    setError(null);
    try {
      const response = await fetch('/api/voice/token', { method: 'POST' });
      const body = (await response.json()) as { token?: string; error?: string };
      if (!response.ok || !body.token) throw new Error(body.error ?? 'Could not start the call.');
      setToken(body.token);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start the call.');
    } finally {
      setConnecting(false);
    }
  }, []);

  const stop = useCallback(() => {
    setToken(null);
    setError(null);
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Talk to KIRRO</CardTitle>
        <CardDescription>
          Speak your declaration. Gnani transcribes you, the agent decides, and Gnani speaks the
          reply back — the same agent, the same connectors, no typing.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {token ? (
          <LiveKitRoom
            serverUrl={serverUrl}
            token={token}
            connect
            // Publishes the microphone and plays the agent through the room.
            audio
            onDisconnected={stop}
            className="flex flex-col gap-4"
          >
            <RoomAudioRenderer />
            <Call />
            <Button variant="outline" className="w-fit" onClick={stop}>
              End call
            </Button>
          </LiveKitRoom>
        ) : (
          <div className="flex items-center gap-3">
            <Button onClick={start} disabled={connecting}>
              {connecting ? 'Connecting…' : 'Start call'}
            </Button>
            <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
              Not connected
            </span>
          </div>
        )}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <p className="text-xs text-muted-foreground">
          Your browser will ask for the microphone. One call at a time — the agent keeps a single
          conversation.
        </p>
      </CardContent>
    </Card>
  );
}
