import { describe, expect, it } from 'vitest';

import { formatCountdown } from '@/lib/kirro/countdown';

describe('formatCountdown', () => {
  it('shows M:SS under an hour', () => {
    expect(formatCountdown(0)).toBe('0:00');
    expect(formatCountdown(53_000)).toBe('0:53');
    expect(formatCountdown(2 * 60_000 + 53_000)).toBe('2:53');
    expect(formatCountdown(59 * 60_000 + 59_000)).toBe('59:59');
  });

  it('shows H:MM:SS from an hour up', () => {
    expect(formatCountdown(60 * 60_000)).toBe('1:00:00');
    expect(formatCountdown(3 * 3600_000 + 5 * 60_000 + 7_000)).toBe('3:05:07');
    expect(formatCountdown(23 * 3600_000 + 59 * 60_000 + 59_000)).toBe('23:59:59');
  });

  it('shows days beyond 24 hours, rather than an absurd minute count', () => {
    // The case a seeded release hits: its window is anchored about a day ahead.
    expect(formatCountdown(30 * 3600_000)).toBe('1d 6h');
    expect(formatCountdown(26 * 3600_000 + 39 * 60_000)).toBe('1d 2h');
  });

  it('never goes negative', () => {
    expect(formatCountdown(-5_000)).toBe('0:00');
  });

  it('rounds up, so it only reads 0:00 when the moment has actually passed', () => {
    expect(formatCountdown(1)).toBe('0:01');
    expect(formatCountdown(1_001)).toBe('0:02');
  });
});
