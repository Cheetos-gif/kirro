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

// Server-only: KIRRO Core is never called from the browser. Every page/action that needs it
// runs as a Server Component, Route Handler, or Server Action, which import this module.
export const kirroApi = createApiClient(env.KIRRO_API_URL);
