import { describe, expect, it } from 'vitest';

import { transcriptAsText } from '@/app/talk/talk-client';

/**
 * The copy/download format is the thing a person pastes elsewhere, so its shape is worth pinning:
 * one speaker-prefixed line per turn, blank-line separated, with the call time in a header when
 * known.
 */
describe('transcriptAsText', () => {
  it('prefixes each turn with its speaker, in order', () => {
    const text = transcriptAsText(
      [
        { mine: true, text: 'I want a tennis court on Saturday' },
        { mine: false, text: 'Which date do you want?' },
        { mine: true, text: 'the 3rd of October' },
      ],
      null,
    );
    expect(text).toBe(
      'You: I want a tennis court on Saturday\n\n' +
        'KIRRO: Which date do you want?\n\n' +
        'You: the 3rd of October\n',
    );
  });

  it('omits the header when the call start is unknown', () => {
    expect(transcriptAsText([{ mine: false, text: 'hello' }], null).startsWith('KIRRO:')).toBe(true);
  });

  it('dates the transcript when the start is known', () => {
    const text = transcriptAsText([{ mine: true, text: 'hi' }], new Date('2026-10-03T09:15:00Z'));
    expect(text).toContain('KIRRO voice transcript —');
    expect(text.endsWith('You: hi\n')).toBe(true);
  });

  it('is newline-terminated so a paste does not run into the next line', () => {
    expect(transcriptAsText([{ mine: true, text: 'hi' }], null).endsWith('\n')).toBe(true);
  });
});
