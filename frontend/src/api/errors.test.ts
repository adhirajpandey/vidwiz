import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { describe, expect, it } from 'vitest';
import {
  getValidationFieldErrors,
  normalizeApiError,
  normalizeFetchError,
} from './errors';
import { markSessionExpiredHandled } from './session';

function createAxiosError(data: unknown, status = 400): AxiosError {
  const config: InternalAxiosRequestConfig = {
    headers: new AxiosHeaders(),
  };
  const response: AxiosResponse = {
    data,
    status,
    statusText: 'Request failed',
    headers: {},
    config,
  };

  return new AxiosError(
    'Request failed',
    AxiosError.ERR_BAD_RESPONSE,
    config,
    undefined,
    response
  );
}

describe('normalizeApiError', () => {
  it('extracts the canonical backend error envelope', () => {
    const cause = createAxiosError(
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
    const cause = createAxiosError({ error: 'Account already exists' }, 409);

    expect(normalizeApiError(cause, 'Registration failed')).toStrictEqual({
      status: 409,
      message: 'Account already exists',
      kind: 'conflict',
      retryable: false,
    });
  });

  it('uses a top-level response message when present', () => {
    const cause = createAxiosError({ message: 'Request could not be completed' });

    expect(normalizeApiError(cause, 'Request failed')).toStrictEqual({
      status: 400,
      message: 'Request could not be completed',
      kind: 'client',
      retryable: false,
    });
  });

  it('falls back for malformed response data', () => {
    const cause = createAxiosError({ error: { message: 42 }, message: false }, 500);

    expect(normalizeApiError(cause, 'Unexpected server response')).toStrictEqual({
      status: 500,
      message: 'Unexpected server response',
      kind: 'server',
      retryable: true,
    });
  });

  it('ignores a malformed HTTP status at runtime', () => {
    const cause = {
      isAxiosError: true,
      response: {
        status: '401',
        data: { error: 'Authentication failed' },
      },
    };

    expect(normalizeApiError(cause, 'Request failed')).toStrictEqual({
      message: 'Authentication failed',
      kind: 'unknown',
      retryable: false,
    });
  });

  it('falls back for an Axios network error without a response', () => {
    const cause = new AxiosError('Network Error', AxiosError.ERR_NETWORK);

    expect(normalizeApiError(cause, 'Could not connect')).toStrictEqual({
      message: 'Could not connect',
      kind: 'network',
      retryable: true,
    });
  });

  it('falls back for a non-Axios thrown value', () => {
    const cause = new Error('Unexpected failure');

    expect(normalizeApiError(cause, 'Something went wrong')).toStrictEqual({
      message: 'Something went wrong',
      kind: 'unknown',
      retryable: false,
    });
  });

  it('hides server-provided messages for 5xx responses and keeps the request ID', () => {
    const cause = createAxiosError(
      {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'OpenRouter API key not configured',
        },
      },
      500
    );
    cause.response!.headers = { 'x-request-id': 'request-123' };

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
    const cause = createAxiosError(
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
      createAxiosError(
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
    const cause = createAxiosError(
      {
        error: {
          code: 'UNAUTHORIZED',
          message: 'Invalid or expired token',
        },
      },
      401
    );
    markSessionExpiredHandled(cause);

    expect(normalizeApiError(cause, 'Please sign in again')).toMatchObject({
      kind: 'authentication',
      handled: true,
    });
  });
});
