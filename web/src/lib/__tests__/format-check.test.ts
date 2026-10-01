import { describe, expect, it } from 'vitest';

import { parseCheckName } from '../format-check';

describe('parseCheckName', () => {
  it('returns null for a builtin (plain-English) name', () => {
    expect(parseCheckName('no success claim before CONFIRMED')).toBeNull();
  });

  it('parses a plain check into key-value pairs', () => {
    expect(parseCheckName('{"type": "final_state", "equals": "CLOSED"}')).toEqual({
      type: 'final_state',
      equals: 'CLOSED',
    });
  });

  it('marks a forbidden_checks entry and strips the prefix', () => {
    expect(parseCheckName('forbidden: {"type": "final_state", "equals": "FAILED"}')).toEqual({
      forbidden: true,
      type: 'final_state',
      equals: 'FAILED',
    });
  });

  it('returns null for malformed JSON', () => {
    expect(parseCheckName('{not json')).toBeNull();
  });

  it('returns null for a JSON array or primitive', () => {
    expect(parseCheckName('[1,2,3]')).toBeNull();
    expect(parseCheckName('42')).toBeNull();
  });
});
