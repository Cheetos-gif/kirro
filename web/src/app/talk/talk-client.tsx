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
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export type TranscriptLine = { key: string; mine: boolean; text: string };

const STATE_LABEL: Record<string, string> = {
  initializing: 'Connecting…',
  idle: 'Listening',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
};

/** Plain text for the clipboard and the download — one line per turn, speaker-prefixed. */
export function transcriptAsText(lines: TranscriptLine[], startedAt: Date | null): string {
  const header = startedAt ? `KIRRO voice transcript — ${startedAt.toLocaleString()}\n\n` : '';
  return header + lines.map(line => `${line.mine ? 'You' : 'KIRRO'}: ${line.text}`).join('\n\n') + '\n';
}

/**
 * Fold one incoming segment into the log, in place.
 *
 * LiveKit does not hand over a finished sentence: it re-emits the same utterance as it grows
 * ("Hello!", "Hello! How", "Hello! How can", …). Appending each revision — the obvious reading —
 * produced a transcript of twelve near-identical lines for one sentence. So a revision **replaces**
 * the line it belongs to, and only a new segment appends.
 */
export function mergeTurn(lines: TranscriptLine[], turn: TranscriptLine): TranscriptLine[] {
  const index = lines.findIndex(line => line.key === turn.key);
  if (index !== -1) {
    const next = [...lines];
    next[index] = { ...next[index], text: turn.text };
    return next;
  }
  // Fallback for a stream that carries no segment id (each revision a new id): the previous line
  // from the same speaker growing by prefix is the same utterance, not a second one.
  const last = lines[lines.length - 1];
  if (last && last.mine === turn.mine && last.text && turn.text.startsWith(last.text)) {
    const next = [...lines];
    next[next.length - 1] = { ...last, text: turn.text };
    return next;
  }
  return [...lines, turn];
}

/**
 * Inside the room: publishes the microphone, renders the visualiser, and reports each finished turn
 * up to the parent so the transcript outlives the call.
 */
function Call({ onTurn }: { onTurn: (line: TranscriptLine) => void }) {
  const { state, audioTrack } = useVoiceAssistant();
  const connection = useConnectionState();
  const transcriptions = useTranscriptions();
  const { localParticipant } = useLocalParticipant();

  useEffect(() => {
    for (const line of transcriptions) {
      const mine = line.participantInfo.identity === localParticipant.identity;
      // One utterance keeps one identity across its revisions: the transcription stream carries
      // `lk.segment_id`, and the stream id is the fallback.
      const segment = line.streamInfo.attributes?.['lk.segment_id'] ?? line.streamInfo.id;
      onTurn({ key: `${mine ? 'me' : 'them'}|${segment}`, mine, text: line.text });
    }
  }, [transcriptions, localParticipant.identity, onTurn]);

  const label =
    connection === ConnectionState.Connected
      ? (STATE_LABEL[state] ?? state)
      : connection === ConnectionState.Connecting
        ? 'Connecting…'
        : 'Not connected';

  return (
    <>
      <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <BarVisualizer
        state={state}
        trackRef={audioTrack}
        barCount={44}
        className="h-24 w-full rounded-2xl border border-border bg-muted/20 px-4 [--lk-fg:var(--primary)]"
      />
    </>
  );
}

export function TalkClient({ serverUrl }: { serverUrl: string }) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [copied, setCopied] = useState(false);
  const [startedAt, setStartedAt] = useState<Date | null>(null);
  const scrollBox = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollBox.current?.scrollTo({ top: scrollBox.current.scrollHeight });
  }, [lines]);

  const onTurn = useCallback((line: TranscriptLine) => {
    setLines(previous => mergeTurn(previous, line));
  }, []);

  const start = useCallback(async () => {
    setConnecting(true);
    setError(null);
    // A new call is a new conversation, so the log starts empty too.
    setLines([]);
    setCopied(false);
    setStartedAt(new Date());
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

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(transcriptAsText(lines, startedAt));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('The browser blocked clipboard access. Select the text and copy it by hand.');
    }
  }, [lines, startedAt]);

  const download = useCallback(() => {
    const blob = new Blob([transcriptAsText(lines, startedAt)], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kirro-transcript-${(startedAt ?? new Date()).toISOString().slice(0, 19).replace(/[:T]/g, '-')}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }, [lines, startedAt]);

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
            audio
            onDisconnected={stop}
            className="flex flex-col gap-4"
          >
            <RoomAudioRenderer />
            <Call onTurn={onTurn} />
            <Button variant="outline" className="w-fit" onClick={stop}>
              End call
            </Button>
          </LiveKitRoom>
        ) : (
          <div className="flex items-center gap-3">
            <Button onClick={start} disabled={connecting}>
              {connecting ? 'Connecting…' : lines.length ? 'Start again' : 'Start call'}
            </Button>
            <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
              Not connected
            </span>
          </div>
        )}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
              Transcript{lines.length ? ` · ${lines.length} turns` : ''}
            </h2>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="xs" onClick={copy} disabled={!lines.length}>
                {copied ? 'Copied' : 'Copy'}
              </Button>
              <Button variant="ghost" size="xs" onClick={download} disabled={!lines.length}>
                Download
              </Button>
            </div>
          </div>

          {/* selectable on purpose: if the clipboard API is blocked, the text is still there to grab */}
          <div
            ref={scrollBox}
            aria-live="polite"
            className="max-h-80 min-h-24 overflow-y-auto rounded-2xl border border-border p-4"
          >
            {lines.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing yet. Say what you want to book — the event, the date, your group size, and
                the most you will pay per person.
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {lines.map((line, index) => (
                  <li key={index} className="text-sm">
                    <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
                      {line.mine ? 'You' : 'KIRRO'}
                    </span>
                    <p className={line.mine ? 'text-muted-foreground' : 'text-foreground'}>
                      {line.text}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <p className="text-xs text-muted-foreground">
          Your browser will ask for the microphone. One call at a time — the agent keeps a single
          conversation.
        </p>
      </CardContent>
    </Card>
  );
}
