'use client';

import {
  BarVisualizer,
  ChatEntry,
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
  VoiceAssistantControlBar,
} from '@livekit/components-react';
import '@livekit/components-styles';
import type { ReceivedChatMessage } from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';
import type { TextStreamReader } from 'livekit-client';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export type TranscriptLine = { key: string; mine: boolean; text: string; at: number };

/** The worker's own topic for the per-call id (voice_bridge/agent.py: CALL_ID_TOPIC). */
const CALL_ID_TOPIC = 'kirro.call_id';
/** Voice-output health, also published by the worker (voice_bridge/agent.py). */
const VOICE_ERROR_TOPIC = 'kirro.voice_error';
const VOICE_OK_TOPIC = 'kirro.voice_ok';

/** Shown when the worker's failure payload carries no message of its own. */
const DEFAULT_VOICE_NOTICE = 'KIRRO is having trouble speaking right now. Your words are still being heard.';

/** Kirro's own WhatsApp Business number. The draw result is delivered here, but only inside a 24-hour
 * window the user opens themselves by messaging first, so the CTA below exists to make that one message
 * easy to send, right after a reservation succeeds. */
const KIRRO_WHATSAPP_NUMBER = '918167312268';

/** The agent's own wording for a successful declaration (agent-spec.md section 3, STEP 4.4): "Rs <amount> is
 * reserved, not charged". Matching on it is a pure display heuristic: it only decides whether to show a
 * popup, never anything about the booking itself, so a false negative just means no popup. */
export const RESERVATION_SUCCESS_PATTERN = /reserved,\s*not charged/i;

/** The `wa.me` deep link that opens WhatsApp with the opening message already typed. */
export function whatsAppLink(text: string): string {
  return `https://wa.me/${KIRRO_WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
}

/**
 * What the user's one opening message says. The agent's confirmation names the booking
 * ("...in the draw for tennis on 10 October..."), so the message repeats that when it is there and
 * falls back to a plain hello otherwise — the send is what matters (it opens the 24-hour window the
 * result is delivered inside), but a thread that names the booking is easier to follow.
 */
export function whatsAppOpeningMessage(confirmation: string | null): string {
  const named = confirmation?.match(/in the draw for (.+?) on ([^.,]+)/i);
  return named
    ? `Hi Kirro! I've entered the draw for ${named[1].trim()} on ${named[2].trim()}. Please send my result here.`
    : "Hi Kirro! I've entered the draw. Please send my result here.";
}

const STATE_LABEL: Record<string, string> = {
  initializing: 'Connecting…',
  idle: 'Listening',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
};

/** Plain text for the clipboard and the download — one line per turn, speaker-prefixed. */
export function transcriptAsText(
  lines: TranscriptLine[],
  startedAt: Date | null,
  callId: string | null = null
): string {
  const started = startedAt ? `KIRRO voice transcript — ${startedAt.toLocaleString()}\n` : '';
  const id = callId ? `Call id: ${callId}\n` : '';
  const header = started || id ? `${started}${id}\n` : '';
  return header + lines.map(line => `${line.mine ? 'You' : 'KIRRO'}: ${line.text}`).join('\n\n') + '\n';
}

/**
 * Fold one incoming message into the log, in place.
 *
 * LiveKit hands over each utterance as a stream of revisions ("Hello!", "Hello! How", "Hello! How
 * can", …) and the agent's TTS-aligned transcript opens a new stream per revision, so the message
 * id alone does not group them. Keying on the segment and rewriting the line it belongs to is what
 * keeps one sentence from becoming twelve lines; only a genuinely new turn appends.
 */
export function mergeTurn(lines: TranscriptLine[], turn: TranscriptLine): TranscriptLine[] {
  const index = lines.findIndex(line => line.key === turn.key);
  if (index !== -1) {
    const next = [...lines];
    next[index] = { ...next[index], text: turn.text };
    return next;
  }
  // A prefix growth from the same speaker is the same utterance still being recognised, not a
  // second one.
  const last = lines[lines.length - 1];
  if (last && last.mine === turn.mine && last.text && turn.text.startsWith(last.text)) {
    const next = [...lines];
    next[next.length - 1] = { ...last, text: turn.text };
    return next;
  }
  return [...lines, turn];
}

/**
 * Inside the room. LiveKit owns the transcript, the turn state, the visualiser and the controls;
 * this only maps its messages into the shape the page keeps for copying.
 */
function Call({
  onTurn,
  onCallId,
  onVoiceError,
  onReserved,
}: {
  onTurn: (line: TranscriptLine) => void;
  onCallId: (id: string) => void;
  onVoiceError: (notice: string | null) => void;
  onReserved: (confirmation: string) => void;
}) {
  const { state, audioTrack } = useVoiceAssistant();
  const connection = useConnectionState();
  // `useTranscriptions` rather than `useSessionMessages`: the latter is beta and returns nothing
  // outside a `SessionProvider`, which this page does not use — measured on the deployed page, an
  // empty transcript with every message dropped.
  const transcriptions = useTranscriptions();
  const { localParticipant } = useLocalParticipant();
  const room = useRoomContext();
  const reservedRef = useRef(false);

  // The worker mints one id per call and sends it on `kirro.call_id`, so the id shown here is the
  // one its conversation log is filed under.
  useEffect(() => {
    const handler = (reader: TextStreamReader) => {
      void reader.readAll().then(id => {
        const trimmed = id.trim();
        if (trimmed) onCallId(trimmed);
      });
    };
    room.registerTextStreamHandler(CALL_ID_TOPIC, handler);
    return () => room.unregisterTextStreamHandler(CALL_ID_TOPIC);
  }, [room, onCallId]);

  useEffect(() => {
    for (const line of transcriptions) {
      const mine = line.participantInfo.identity === localParticipant.identity;
      // `lk.segment_id` groups an utterance across its revisions; the stream id is the fallback.
      const segment = line.streamInfo.attributes?.['lk.segment_id'] ?? line.streamInfo.id;
      onTurn({
        key: `${mine ? 'me' : 'them'}|${segment}`,
        mine,
        text: line.text,
        at: line.streamInfo.timestamp ?? 0,
      });
      // A display-only heuristic (see RESERVATION_SUCCESS_PATTERN): the agent's own reservation
      // wording is what triggers the WhatsApp CTA, never anything this page decides on its own. Once
      // per call — LiveKit re-emits a segment as it is revised, and the popup must not reopen after
      // the user has dismissed it.
      if (!mine && !reservedRef.current && RESERVATION_SUCCESS_PATTERN.test(line.text)) {
        reservedRef.current = true;
        onReserved(line.text);
      }
    }
  }, [transcriptions, localParticipant.identity, onTurn, onReserved]);

  // Gnani's TTS does return 500s mid-call, and the caller otherwise just hears silence with no way
  // to tell a vendor outage apart from a stalled agent. The worker publishes the failure, and a
  // completed synthesis clears it, so the notice disappears by itself when speech resumes.
  useEffect(() => {
    const onFailure = (reader: TextStreamReader) => {
      void reader.readAll().then(raw => {
        let detail = DEFAULT_VOICE_NOTICE;
        try {
          const parsed = JSON.parse(raw) as { message?: string };
          detail = parsed.message || DEFAULT_VOICE_NOTICE;
        } catch {
          // A non-JSON payload still means a failure; the default line stands on its own.
        }
        onVoiceError(detail);
      });
    };
    const onRecovered = (reader: TextStreamReader) => {
      void reader.readAll().then(() => onVoiceError(null));
    };
    room.registerTextStreamHandler(VOICE_ERROR_TOPIC, onFailure);
    room.registerTextStreamHandler(VOICE_OK_TOPIC, onRecovered);
    return () => {
      room.unregisterTextStreamHandler(VOICE_ERROR_TOPIC);
      room.unregisterTextStreamHandler(VOICE_OK_TOPIC);
    };
  }, [room, onVoiceError]);

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
      <VoiceAssistantControlBar />
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
  const [callId, setCallId] = useState<string | null>(null);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const [whatsAppText, setWhatsAppText] = useState<string | null>(null);
  const scrollBox = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollBox.current?.scrollTo({ top: scrollBox.current.scrollHeight });
  }, [lines]);

  const onTurn = useCallback((line: TranscriptLine) => {
    setLines(previous => mergeTurn(previous, line));
  }, []);

  const onCallId = useCallback((id: string) => {
    setCallId(id);
  }, []);

  const onVoiceError = useCallback((detail: string | null) => {
    setVoiceNotice(detail);
  }, []);

  const onReserved = useCallback((confirmation: string) => {
    setWhatsAppText(whatsAppOpeningMessage(confirmation));
  }, []);

  const start = useCallback(async () => {
    setConnecting(true);
    setError(null);
    // A new call is a new conversation, so the log starts empty too.
    setLines([]);
    setCopied(false);
    setCallId(null);
    setVoiceNotice(null);
    setWhatsAppText(null);
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
      await navigator.clipboard.writeText(transcriptAsText(lines, startedAt, callId));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('The browser blocked clipboard access. Select the text and copy it by hand.');
    }
  }, [lines, startedAt, callId]);

  const download = useCallback(() => {
    const blob = new Blob([transcriptAsText(lines, startedAt, callId)], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kirro-transcript-${(startedAt ?? new Date()).toISOString().slice(0, 19).replace(/[:T]/g, '-')}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }, [lines, startedAt, callId]);

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
            <Call onTurn={onTurn} onCallId={onCallId} onVoiceError={onVoiceError} onReserved={onReserved} />
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

        {voiceNotice ? (
          <p
            role="status"
            className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-600 dark:text-amber-400"
          >
            {voiceNotice}
          </p>
        ) : null}

        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <h2 className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
                Transcript{lines.length ? ` · ${lines.length} turns` : ''}
              </h2>
              {callId ? (
                <span
                  className="truncate font-mono text-xs text-muted-foreground"
                  title={`Conversation id: ${callId} — quote it when reporting a problem with this call.`}
                >
                  {callId}
                </span>
              ) : null}
            </div>
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
                {lines.map(line => (
                  <li key={line.key} className="flex flex-col gap-0.5">
                    <span className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
                      {line.mine ? 'You' : 'KIRRO'}
                    </span>
                    {/* LiveKit's own entry markup and styling for the message body. */}
                    <ChatEntry
                      entry={
                        {
                          id: line.key,
                          timestamp: line.at,
                          message: line.text,
                        } as unknown as ReceivedChatMessage
                      }
                      hideName
                    />
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

      {whatsAppText ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="wa-popup-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        >
          <Card className="w-full max-w-sm">
            <CardHeader>
              <CardTitle id="wa-popup-title">One tap to get your result</CardTitle>
              <CardDescription>
                You&apos;re in the draw. WhatsApp only lets a business message you once you&apos;ve
                messaged it first, so send this one message and the result will reach you there after
                the window closes.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                {whatsAppText}
              </p>
              <Button
                render={<a href={whatsAppLink(whatsAppText)} target="_blank" rel="noreferrer" />}
                nativeButton={false}
                className="w-full"
              >
                Open WhatsApp
              </Button>
              <Button variant="ghost" className="w-fit" onClick={() => setWhatsAppText(null)}>
                Not now
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </Card>
  );
}
