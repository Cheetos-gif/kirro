import axios from 'axios';

import { API_TIMEOUT_MS } from '@/constants';
import { env } from '@/env';

import { toApiError } from './errors';

export function createApiClient(baseURL: string) {
  const client = axios.create({
    baseURL,
    headers: { 'Content-Type': 'application/json' },
    timeout: API_TIMEOUT_MS,
  });

  client.interceptors.response.use(
    response => response,
    error => Promise.reject(toApiError(error))
  );

  return client;
}

/**
 * The app's single client, aimed at `mock_server`. Every request carries `X-Run-Id`, the mock's per-run
 * correlation header — that is what scopes state to one demo run.
 */
export const api = createApiClient(env.MOCK_API_URL);

api.interceptors.request.use(config => {
  config.headers.set('X-Run-Id', env.MOCK_RUN_ID);
  return config;
});
