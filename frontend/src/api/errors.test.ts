import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  getValidationFieldErrors,
  normalizeApiError,
  normalizeFetchError,
  toastApiError,
} from './errors';
import { ApiError } from './fetch';
import { markSessionExpiredHandled } from './session';

afterEach(() => {
  vi.useRealTimers();
});

function createApiError(
  data: unknown,
  status = 400,
  headers: Record<string, string> = {}
): ApiError {
  return new ApiError(new Response(null, { status, headers }), data);
}

describe('normalizeApiError', () => {
  it('extracts the canonical backend error envelope', () => {
    const cause = createApiError(
      {
        error: {
          code: 'invalid_credentials',
          message: 'Email or password is incorrect',
          details: { field: 'password' },
        },
      },
      401
    );

    expect(normalizeApiError(cause, 'Login failed')).toStrictEqual({
      status: 401,
      code: 'invalid_credentials',
      message: 'Email or password is incorrect',
      details: { field: 'password' },
      kind: 'authentication',
      retryable: false,
    });
  });

  it('supports a legacy string error response', () => {
    const cause = createApiError({ error: 'Account already exists' }, 409);

    expect(normalizeApiError(cause, 'Registration failed')).toStrictEqual({
      status: 409,
      message: 'Account already exists',
      kind: 'conflict',
      retryable: false,
    });
  });

  it('uses a top-level response message when present', () => {
    const cause = createApiError({ message: 'Request could not be completed' });

    expect(normalizeApiError(cause, 'Request failed')).toStrictEqual({
      status: 400,
      message: 'Request could not be completed',
      kind: 'client',
      retryable: false,
    });
  });

  it('falls back for malformed response data', () => {
    const cause = createApiError({ error: { message: 42 }, message: false }, 500);

    expect(normalizeApiError(cause, 'Unexpected server response')).toStrictEqual({
      status: 500,
      message: 'Unexpected server response',
      kind: 'server',
      retryable: true,
    });
  });

  it('treats a rejected fetch as a network error', () => {
    const cause = new TypeError('Failed to fetch');

    expect(normalizeApiError(cause, 'Could not connect')).toStrictEqual({
      message: 'Could not connect',
      kind: 'network',
      retryable: true,
    });
  });

  it('falls back for any other thrown value', () => {
    const cause = new Error('Unexpected failure');

    expect(normalizeApiError(cause, 'Something went wrong')).toStrictEqual({
      message: 'Something went wrong',
      kind: 'unknown',
      retryable: false,
    });
  });

  it('hides server-provided messages for 5xx responses and keeps the request ID', () => {
    const cause = createApiError(
      {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'OpenRouter API key not configured',
        },
      },
      500,
      { 'x-request-id': 'request-123' }
    );

    expect(normalizeApiError(cause, 'Chat is temporarily unavailable')).toStrictEqual({
      status: 500,
      code: 'INTERNAL_ERROR',
      message: 'Chat is temporarily unavailable',
      requestId: 'request-123',
      kind: 'server',
      retryable: true,
    });
  });

  it('preserves validated field-level validation details', () => {
    const cause = createApiError(
      {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Request validation failed',
          details: [
            {
              field: 'body.email',
              message: 'value is not a valid email address',
              type: 'value_error',
            },
          ],
        },
      },
      422
    );

    expect(normalizeApiError(cause, 'Please check your details')).toMatchObject({
      kind: 'validation',
      details: [
        {
          field: 'body.email',
          message: 'value is not a valid email address',
          type: 'value_error',
        },
      ],
    });
  });

  it('maps backend validation paths to form field names', () => {
    const error = normalizeApiError(
      createApiError(
        {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Request validation failed',
            details: [
              { field: 'body.email', message: 'Enter a valid email' },
              { field: 'body.name', message: 'Name is too short' },
            ],
          },
        },
        422
      ),
      'Please check your details'
    );

    expect(getValidationFieldErrors(error)).toStrictEqual({
      email: 'Enter a valid email',
      name: 'Name is too short',
    });
  });

  it('normalizes fetch errors and reads request and retry headers', async () => {
    const response = new Response(
      JSON.stringify({
        error: {
          code: 'RATE_LIMIT_EXCEEDED',
          message: 'Daily limit reached',
        },
      }),
      {
        status: 429,
        headers: {
          'Content-Type': 'application/json',
          'Retry-After': '42',
          'X-Request-ID': 'request-429',
        },
      }
    );

    await expect(normalizeFetchError(response, 'Please try again later')).resolves.toStrictEqual({
      status: 429,
      code: 'RATE_LIMIT_EXCEEDED',
      message: 'Daily limit reached',
      requestId: 'request-429',
      retryAfterSeconds: 42,
      kind: 'rate_limit',
      retryable: true,
    });
  });

  it('supports an HTTP-date Retry-After header', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-27T10:00:00Z'));
    const response = new Response(
      JSON.stringify({ error: { message: 'Try later' } }),
      {
        status: 429,
        headers: {
          'Content-Type': 'application/json',
          'Retry-After': 'Mon, 27 Jul 2026 10:00:42 GMT',
        },
      }
    );

    await expect(normalizeFetchError(response, 'Try later')).resolves.toMatchObject({
      retryAfterSeconds: 42,
    });
  });

  it.each([
    'Mon, 27 Jul 2026 09:59:59 GMT',
    'not-a-date',
  ])('ignores an invalid or past Retry-After value: %s', async (retryAfter) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-27T10:00:00Z'));
    const response = new Response(
      JSON.stringify({ error: { message: 'Try later' } }),
      {
        status: 429,
        headers: {
          'Content-Type': 'application/json',
          'Retry-After': retryAfter,
        },
      }
    );

    await expect(normalizeFetchError(response, 'Try later')).resolves.not.toHaveProperty(
      'retryAfterSeconds'
    );
  });

  it('uses a safe fallback for a non-JSON fetch server error', async () => {
    const response = new Response('<html>Bad gateway</html>', {
      status: 502,
      statusText: 'Bad Gateway',
    });

    await expect(normalizeFetchError(response, 'Service is temporarily unavailable')).resolves.toStrictEqual({
      status: 502,
      message: 'Service is temporarily unavailable',
      kind: 'server',
      retryable: true,
    });
  });

  it('marks centrally handled session errors so pages stay silent', () => {
    const cause = createApiError(
      {
        error: {
          code: 'UNAUTHORIZED',
          message: 'Invalid or expired token',
        },
      },
      401
    );
    markSessionExpiredHandled(cause.response);

    expect(normalizeApiError(cause, 'Please sign in again')).toMatchObject({
      kind: 'authentication',
      handled: true,
    });
  });
});

describe('toastApiError', () => {
  it('shows the normalized message with its request ID', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const addToast = vi.fn();
    const cause = createApiError({ error: { message: 'Name is taken' } }, 409, {
      'x-request-id': 'request-409',
    });

    expect(toastApiError(addToast, cause, 'Unable to save', 'Save failed')).toMatchObject({
      kind: 'conflict',
    });
    expect(addToast).toHaveBeenCalledWith({
      title: 'Unable to save',
      message: 'Name is taken',
      type: 'error',
      referenceId: 'request-409',
    });
  });

  it('stays silent for centrally handled session errors', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const addToast = vi.fn();
    const cause = createApiError({ error: { message: 'Expired' } }, 401);
    markSessionExpiredHandled(cause.response);

    expect(toastApiError(addToast, cause, 'Unable to save', 'Save failed').handled).toBe(true);
    expect(addToast).not.toHaveBeenCalled();
  });
});
