import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getDeclarationFull, listDeclarations } from '../kirro';

const { fakeClient } = vi.hoisted(() => ({ fakeClient: { request: vi.fn() } }));

// Replace only the transport: the real `request()` (and therefore the real schema validation) still runs.
vi.mock('@/api/client', () => ({
  createApiClient: () => fakeClient,
  kirroApi: fakeClient,
}));

const validState = {
  declaration_id: 'decl-1',
  state: 'INTAKE',
  confirmed_fields: {},
  open_field: null,
  open_field_note: null,
  readback_presented: false,
  allowed_actions: [],
  booking_ref: null,
};

beforeEach(() => fakeClient.request.mockReset());

describe('KIRRO Core read validation', () => {
  it('accepts a well-formed declaration list', async () => {
    fakeClient.request.mockResolvedValue({ data: [validState] });
    await expect(listDeclarations()).resolves.toEqual([validState]);
  });

  it('rejects a declaration missing required fields rather than returning undefineds', async () => {
    fakeClient.request.mockResolvedValue({ data: [{ declaration_id: 'decl-1' }] });
    await expect(listDeclarations()).rejects.toThrow(/validation error/i);
  });

  it('rejects a declaration whose field has the wrong type', async () => {
    fakeClient.request.mockResolvedValue({ data: [{ ...validState, readback_presented: 'yes' }] });
    await expect(listDeclarations()).rejects.toThrow(/validation error/i);
  });

  it('rejects a /full payload that is not the declaration shape', async () => {
    fakeClient.request.mockResolvedValue({ data: { declaration_id: 'decl-1' } });
    await expect(getDeclarationFull('decl-1')).rejects.toThrow(/validation error/i);
  });

  it('reports a non-JSON error body as a reached-but-failed call', async () => {
    fakeClient.request.mockResolvedValue({ data: '<html>502 Bad Gateway</html>' });
    await expect(listDeclarations()).rejects.toThrow(/validation error/i);
  });
});
