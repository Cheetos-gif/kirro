import { describe, expect, it } from 'vitest';

import { RESERVATION_SUCCESS_PATTERN } from '@/app/talk/talk-client';

/**
 * The popup that offers to open WhatsApp is triggered by this pattern matching the agent's own
 * reservation wording, so pin both directions: it must fire on the real confirmation and stay quiet
 * on the near-misses that reach the transcript panel every call.
 */
describe('RESERVATION_SUCCESS_PATTERN', () => {
  const matches = (text: string) => new RegExp(RESERVATION_SUCCESS_PATTERN).test(text);

  it('matches the agent’s own reservation confirmation', () => {
    expect(
      matches(
        'Rs 1,200 is reserved, not charged. You are in the draw for tennis on 10 October. ' +
          'The window opens at 11:30 AM IST on 9 October.',
      ),
    ).toBe(true);
  });

  it('matches regardless of spacing or case', () => {
    expect(matches('Rs 600 is Reserved,  Not Charged.')).toBe(true);
  });

  it('does not match a clarifying question before the reservation', () => {
    expect(matches('Tennis on 10 October, any slot, 2 people, all or nothing. Shall I go ahead?')).toBe(
      false,
    );
  });

  it('does not match a failure or cancellation reply', () => {
    expect(matches('The amount could not be reserved due to insufficient balance.')).toBe(false);
    expect(matches('Your declaration has been cancelled, and Rs 600 has been released.')).toBe(false);
  });
});
