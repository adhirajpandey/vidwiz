import axios from 'axios';

export interface NormalizedApiError {
  status?: number;
  code?: string;
  message: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

export function normalizeApiError(
  cause: unknown,
  fallbackMessage: string
): NormalizedApiError {
  if (!axios.isAxiosError(cause)) {
    return { message: fallbackMessage };
  }

  const normalized: NormalizedApiError = {
    message: fallbackMessage,
  };

  if (
    typeof cause.response?.status === 'number' &&
    Number.isFinite(cause.response.status)
  ) {
    normalized.status = cause.response.status;
  }

  const responseData: unknown = cause.response?.data;
  if (!isRecord(responseData)) {
    return normalized;
  }

  const errorValue = responseData.error;
  if (isRecord(errorValue)) {
    const code = nonEmptyString(errorValue.code);
    if (code) {
      normalized.code = code;
    }
    normalized.message =
      nonEmptyString(errorValue.message) ??
      nonEmptyString(responseData.message) ??
      fallbackMessage;
    return normalized;
  }

  normalized.message =
    nonEmptyString(errorValue) ??
    nonEmptyString(responseData.message) ??
    fallbackMessage;
  return normalized;
}
