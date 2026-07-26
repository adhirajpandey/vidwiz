import axios from 'axios';
import { wasSessionExpiredHandled } from './session';

export type ApiErrorKind =
  | 'authentication'
  | 'authorization'
  | 'validation'
  | 'not_found'
  | 'conflict'
  | 'rate_limit'
  | 'client'
  | 'network'
  | 'server'
  | 'stream'
  | 'unknown';

export interface ApiValidationDetail {
  field?: string;
  message: string;
  type?: string;
}

export type ApiErrorDetails =
  | ApiValidationDetail[]
  | Record<string, unknown>;

export interface NormalizedApiError {
  status?: number;
  code?: string;
  message: string;
  details?: ApiErrorDetails;
  requestId?: string;
  retryAfterSeconds?: number;
  kind: ApiErrorKind;
  retryable: boolean;
  handled?: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function finiteStatus(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : undefined;
}

function errorKind(status: number | undefined): ApiErrorKind {
  switch (status) {
    case 401:
      return 'authentication';
    case 403:
      return 'authorization';
    case 404:
      return 'not_found';
    case 409:
      return 'conflict';
    case 422:
      return 'validation';
    case 429:
      return 'rate_limit';
    default:
      if (status !== undefined && status >= 500) return 'server';
      if (status !== undefined && status >= 400) return 'client';
      return 'unknown';
  }
}

function isRetryable(status: number | undefined, kind: ApiErrorKind): boolean {
  return (
    kind === 'network' ||
    kind === 'server' ||
    status === 408 ||
    status === 425 ||
    status === 429
  );
}

function normalizedDetails(value: unknown): ApiErrorDetails | undefined {
  if (Array.isArray(value)) {
    const details: ApiValidationDetail[] = [];
    for (const item of value) {
      if (!isRecord(item)) return undefined;
      const message = nonEmptyString(item.message);
      if (!message) return undefined;
      const detail: ApiValidationDetail = { message };
      const field = nonEmptyString(item.field);
      const type = nonEmptyString(item.type);
      if (field) detail.field = field;
      if (type) detail.type = type;
      details.push(detail);
    }
    return details;
  }
  return isRecord(value) ? value : undefined;
}

function headerValue(headers: unknown, name: string): string | undefined {
  if (!headers || typeof headers !== 'object') return undefined;

  const getter = (headers as { get?: unknown }).get;
  if (typeof getter === 'function') {
    const value = getter.call(headers, name);
    return nonEmptyString(value);
  }

  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === name.toLowerCase()) {
      return nonEmptyString(value);
    }
  }
  return undefined;
}

function retryAfterSeconds(
  details: ApiErrorDetails | undefined,
  retryAfterHeader: string | undefined
): number | undefined {
  if (details && !Array.isArray(details)) {
    const resetSeconds = details.reset_in_seconds;
    if (
      typeof resetSeconds === 'number' &&
      Number.isFinite(resetSeconds) &&
      resetSeconds >= 0
    ) {
      return Math.floor(resetSeconds);
    }
  }

  if (!retryAfterHeader) return undefined;
  const seconds = Number(retryAfterHeader);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.floor(seconds);
  }

  const retryAt = Date.parse(retryAfterHeader);
  if (!Number.isFinite(retryAt) || retryAt <= Date.now()) return undefined;
  return Math.ceil((retryAt - Date.now()) / 1000);
}

function normalizeResponse(
  responseData: unknown,
  status: number | undefined,
  fallbackMessage: string,
  headers?: unknown
): NormalizedApiError {
  const kind = errorKind(status);
  const normalized: NormalizedApiError = {
    message: fallbackMessage,
    kind,
    retryable: isRetryable(status, kind),
  };
  if (status !== undefined) normalized.status = status;

  const requestId = headerValue(headers, 'x-request-id');
  if (requestId) normalized.requestId = requestId;

  if (!isRecord(responseData)) {
    return normalized;
  }

  const errorValue = responseData.error;
  if (isRecord(errorValue)) {
    const code = nonEmptyString(errorValue.code);
    if (code) normalized.code = code;

    if (status === undefined || status < 500) {
      normalized.message =
        nonEmptyString(errorValue.message) ??
        nonEmptyString(responseData.message) ??
        fallbackMessage;
      const details = normalizedDetails(errorValue.details);
      if (details) normalized.details = details;
    }
  } else if (status === undefined || status < 500) {
    normalized.message =
      nonEmptyString(errorValue) ??
      nonEmptyString(responseData.message) ??
      fallbackMessage;
  }

  const retrySeconds = retryAfterSeconds(
    normalized.details,
    headerValue(headers, 'retry-after')
  );
  if (retrySeconds !== undefined) {
    normalized.retryAfterSeconds = retrySeconds;
  }
  return normalized;
}

export function normalizeApiError(
  cause: unknown,
  fallbackMessage: string
): NormalizedApiError {
  if (!axios.isAxiosError(cause)) {
    return {
      message: fallbackMessage,
      kind: 'unknown',
      retryable: false,
    };
  }

  if (!cause.response) {
    return {
      message: fallbackMessage,
      kind: 'network',
      retryable: true,
    };
  }

  const normalized = normalizeResponse(
    cause.response.data,
    finiteStatus(cause.response.status),
    fallbackMessage,
    cause.response.headers
  );
  if (wasSessionExpiredHandled(cause)) {
    normalized.handled = true;
  }
  return normalized;
}

export async function normalizeFetchError(
  response: Response,
  fallbackMessage: string
): Promise<NormalizedApiError> {
  let responseData: unknown;
  try {
    responseData = await response.json();
  } catch {
    responseData = undefined;
  }

  return normalizeResponse(
    responseData,
    finiteStatus(response.status),
    fallbackMessage,
    response.headers
  );
}

export function getValidationFieldErrors(
  error: NormalizedApiError
): Record<string, string> {
  if (!Array.isArray(error.details)) return {};

  const fieldErrors: Record<string, string> = {};
  for (const detail of error.details) {
    if (!detail.field) continue;
    const field = detail.field.split('.').filter(Boolean).pop();
    if (field && !fieldErrors[field]) {
      fieldErrors[field] = detail.message;
    }
  }
  return fieldErrors;
}
