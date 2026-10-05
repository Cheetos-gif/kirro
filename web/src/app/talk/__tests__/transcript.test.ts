import { describe, expect, it } from 'vitest';

import { mergeTurn, transcriptAsText, type TranscriptLine } from '@/app/talk/talk-client';

/**
 * The copy/download format is the thing a person pastes elsewhere, so its shape is worth pinning:
 * one speaker-prefixed line per turn, blank-line separated, with the call time in a header when
 * known.
 */
describe('transcriptAsText', () => {
  const line = (key: string, mine: boolean, text: string): TranscriptLine => ({
    key,
    mine,
    text,
    at: 0,
  });

  it('prefixes each turn with its speaker, in order', () => {
    const text = transcriptAsText(
      [
        line('me|1', true, 'I want a tennis court on Saturday'),
        line('them|2', false, 'Which date do you want?'),
        line('me|3', true, 'the 3rd of October'),
      ],
      null
    );
    expect(text).toBe(
      'You: I want a tennis court on Saturday\n\n' +
        'KIRRO: Which date do you want?\n\n' +
        'You: the 3rd of October\n'
    );
  });

  it('omits the header when the call start is unknown', () => {
    expect(transcriptAsText([line('them|1', false, 'hello')], null).startsWith('KIRRO:')).toBe(
      true
    );
  });

  it('dates the transcript when the start is known', () => {
    const text = transcriptAsText([line('me|1', true, 'hi')], new Date('2026-10-03T09:15:00Z'));
    expect(text).toContain('KIRRO voice transcript —');
    expect(text.endsWith('You: hi\n')).toBe(true);
  });

  it('is newline-terminated so a paste does not run into the next line', () => {
    expect(transcriptAsText([line('me|1', true, 'hi')], null).endsWith('\n')).toBe(true);
  });

  it('includes the call id in the header when known, for reporting a problem with that call', () => {
    const text = transcriptAsText(
      [line('me|1', true, 'hi')],
      new Date('2026-10-03T09:15:00Z'),
      'call_29fbe992aa8d'
    );
    expect(text).toContain('Call id: call_29fbe992aa8d\n');
    expect(text.startsWith('KIRRO voice transcript —')).toBe(true);
  });

  it('carries only the call id when the start time is unknown', () => {
    const text = transcriptAsText([line('me|1', true, 'hi')], null, 'call_x');
    expect(text).toBe('Call id: call_x\n\nYou: hi\n');
  });
});

/**
 * The bug this exists for: LiveKit streams a sentence as it grows, and appending each revision
 * turned one utterance into a column of near-identical lines.
 */
describe('mergeTurn', () => {
  const line = (key: string, mine: boolean, text: string): TranscriptLine => ({
    key,
    mine,
    text,
    at: 0,
  });

  it('rewrites a growing segment in place instead of appending a line per revision', () => {
    let lines: TranscriptLine[] = [];
    for (const text of [
      'Hello!',
      'Hello! How',
      'Hello! How can',
      'Hello! How can I assist you today with your booking needs?',
    ]) {
      lines = mergeTurn(lines, line('them|seg-1', false, text));
    }
    expect(lines).toHaveLength(1);
    expect(lines[0].text).toBe('Hello! How can I assist you today with your booking needs?');
  });

  it('appends a genuinely new segment', () => {
    let lines = mergeTurn([], line('me|seg-1', true, 'tennis court'));
    lines = mergeTurn(lines, line('them|seg-2', false, 'Which date?'));
    expect(lines.map(l => l.text)).toEqual(['tennis court', 'Which date?']);
  });

  it('keeps order when an earlier segment is revised after a later one arrived', () => {
    let lines = mergeTurn([], line('me|seg-1', true, 'I want a court'));
    lines = mergeTurn(lines, line('them|seg-2', false, 'Which date?'));
    lines = mergeTurn(lines, line('me|seg-1', true, 'I want a tennis court on Saturday'));
    expect(lines.map(l => l.text)).toEqual(['I want a tennis court on Saturday', 'Which date?']);
  });

  it('treats a prefix growth from the same speaker as one utterance when there is no segment id', () => {
    let lines = mergeTurn([], line('them|stream-1', false, 'Hello! How'));
    lines = mergeTurn(lines, line('them|stream-2', false, 'Hello! How can I'));
    expect(lines).toHaveLength(1);
    expect(lines[0].text).toBe('Hello! How can I');
  });

  it('does not merge a different speaker, even on an identical prefix', () => {
    let lines = mergeTurn([], line('me|1', true, 'yes'));
    lines = mergeTurn(lines, line('them|2', false, 'yes please'));
    expect(lines).toHaveLength(2);
  });
});
