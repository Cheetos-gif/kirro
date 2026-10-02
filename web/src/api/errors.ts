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
    // mock_server returns `{"error": {"code", "message", "details"}}`; other error shapes are flat.
    const nested = data?.error as
      { code?: string; message?: string; details?: unknown } | undefined;
    return new ApiError({
      message: nested?.message ?? (data?.message as string | undefined) ?? error.message,
      status,
      code: nested?.code ?? (data?.code as string | undefined),
      details: nested?.details ?? data,
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
