import { describe, expect, it } from 'vitest';

import {
  RESERVATION_SUCCESS_PATTERN,
  whatsAppLink,
  whatsAppOpeningMessage,
} from '@/app/talk/talk-client';

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
          'The window opens at 11:30 AM IST on 9 October.'
      )
    ).toBe(true);
  });

  it('matches the wording a real call produced', () => {
    expect(
      matches(
        'Rs 3,000 is reserved, not charged. You are in the draw for tennis on 10 October. The window ' +
          'opens at 11:30 AM IST on 9 October. The result will reach you on WhatsApp at the number ' +
          'you provided. Please send one message to +91 81673 12268 first, or the result will not arrive.'
      )
    ).toBe(true);
  });

  it('matches regardless of spacing or case', () => {
    expect(matches('Rs 600 is Reserved,  Not Charged.')).toBe(true);
  });

  it('does not match a clarifying question before the reservation', () => {
    expect(
      matches('Tennis on 10 October, any slot, 2 people, all or nothing. Shall I go ahead?')
    ).toBe(false);
  });

  it('does not match a failure or cancellation reply', () => {
    expect(matches('The amount could not be reserved due to insufficient balance.')).toBe(false);
    expect(matches('Your declaration has been cancelled, and Rs 600 has been released.')).toBe(
      false
    );
  });
});

describe('whatsAppOpeningMessage', () => {
  it('names the booking the confirmation gave, so the thread is identifiable', () => {
    const message = whatsAppOpeningMessage(
      'Rs 3,000 is reserved, not charged. You are in the draw for tennis on 10 October. The window opens...'
    );
    expect(message).toBe(
      "Hi Kirro! I've entered the draw for tennis on 10 October. Please send my result here."
    );
  });

  it('falls back to a plain hello when the confirmation names no booking', () => {
    expect(whatsAppOpeningMessage(null)).toBe(
      "Hi Kirro! I've entered the draw. Please send my result here."
    );
    expect(whatsAppOpeningMessage('Rs 600 is reserved, not charged.')).toBe(
      "Hi Kirro! I've entered the draw. Please send my result here."
    );
  });
});

describe('whatsAppLink', () => {
  it('opens WhatsApp on Kirro’s number with the message pre-typed', () => {
    const link = whatsAppLink('Hi Kirro!');
    expect(link.startsWith('https://wa.me/918167312268?text=')).toBe(true);
    expect(decodeURIComponent(link.split('text=')[1])).toBe('Hi Kirro!');
  });

  it('escapes a message that carries punctuation and spaces', () => {
    const link = whatsAppLink("Hi Kirro! I've entered the draw for tennis on 10 October.");
    expect(link).not.toContain(' ');
    expect(decodeURIComponent(link.split('text=')[1])).toContain("I've entered the draw");
  });
});
