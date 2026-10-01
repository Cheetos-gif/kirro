import { describe, expect, it } from 'vitest';

import { isEmptyDetail, parseCheckName } from '../format-check';

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

describe('isEmptyDetail', () => {
  it('treats an empty Python list/dict repr as empty', () => {
    expect(isEmptyDetail('[]')).toBe(true);
    expect(isEmptyDetail('{}')).toBe(true);
    expect(isEmptyDetail('')).toBe(true);
    expect(isEmptyDetail('  []  ')).toBe(true);
  });

  it('treats a real value as not empty', () => {
    expect(isEmptyDetail('create_hold called 1x')).toBe(false);
    expect(isEmptyDetail("['AWAITING_USER', 'CLOSED']")).toBe(false);
  });
});
