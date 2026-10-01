import { describe, expect, it } from 'vitest';

import { describeOpenField } from '../declare-messages';

describe('describeOpenField', () => {
  it('explains an ambiguous field with a known label', () => {
    expect(describeOpenField('max_price', 'ambiguous')).toBe(
      'Give one clear answer for the max price per person'
    );
  });

  it('explains an invalid field', () => {
    expect(describeOpenField('date', 'invalid')).toBe(
      "Couldn't understand the date — try rephrasing"
    );
  });

  it('falls back to the raw field name for an unknown field key', () => {
    expect(describeOpenField('some_new_field', 'ambiguous')).toBe(
      'Give one clear answer for some_new_field'
    );
  });

  it('uses the note verbatim when it is neither ambiguous nor invalid', () => {
    expect(describeOpenField('event', 'unresolved')).toBe('what you want to book: unresolved');
  });

  it('falls back to "Still need" when there is no note at all', () => {
    expect(describeOpenField('group_size', null)).toBe('Still need the group size');
  });
});
