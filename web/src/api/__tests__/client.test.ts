import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../client';

vi.mock('@/env', () => ({
  env: {
    MOCK_API_URL: 'http://127.0.0.1:8081',
    MOCK_RUN_ID: 'default',
    MOCK_ADMIN_KEY: 'test-admin-key',
  },
}));

describe('api client admin header', () => {
  it('attaches X-Admin-Key to /__admin/* requests when MOCK_ADMIN_KEY is set', async () => {
    const fulfilled = api.interceptors.request.handlers?.[0]?.fulfilled;
    if (!fulfilled) throw new Error('expected a request interceptor to be registered');

    const config = await fulfilled({ url: '/__admin/state', headers: new AxiosHeaders() });
    expect(config.headers.get('X-Admin-Key')).toBe('test-admin-key');
  });

  it('does not attach X-Admin-Key to non-admin requests', async () => {
    const fulfilled = api.interceptors.request.handlers?.[0]?.fulfilled;
    if (!fulfilled) throw new Error('expected a request interceptor to be registered');

    const config = await fulfilled({ url: '/venue/events', headers: new AxiosHeaders() });
    expect(config.headers.get('X-Admin-Key')).toBeUndefined();
  });
});
