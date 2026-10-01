import { isAxiosError } from 'axios';
import { ZodError } from 'zod';

import type { ApiErrorData } from '@/types';

export class ApiError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly details?: unknown;

  constructor({ message, status, code, details }: ApiErrorData) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function toApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;

  if (isAxiosError(error)) {
    const status = error.response?.status;
    const data = error.response?.data as Record<string, unknown> | undefined;
    // A connection-level failure (refused, reset, timeout, DNS) never reaches `error.response`,
    // and Node's AggregateError for ECONNREFUSED has an empty top-level `.message` — the only
    // useful signal is axios's own `error.code`. Without this fallback the user sees "".
    const message =
      (data?.message as string | undefined) ??
      (error.message || `Request failed: ${error.code ?? 'unknown error'}`);
    return new ApiError({
      message,
      status,
      code: (data?.code as string | undefined) ?? error.code,
      details: data,
    });
  }

  if (error instanceof ZodError) {
    return new ApiError({
      message: 'Validation error',
      code: 'VALIDATION_ERROR',
      details: error.issues,
    });
  }

  if (error instanceof Error) {
    return new ApiError({ message: error.message });
  }

  return new ApiError({ message: 'An unexpected error occurred' });
}
