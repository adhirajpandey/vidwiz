import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { describe, expect, it } from 'vitest';
import { normalizeApiError } from './errors';

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
    });
  });

  it('supports a legacy string error response', () => {
    const cause = createAxiosError({ error: 'Account already exists' }, 409);

    expect(normalizeApiError(cause, 'Registration failed')).toStrictEqual({
      status: 409,
      message: 'Account already exists',
    });
  });

  it('uses a top-level response message when present', () => {
    const cause = createAxiosError({ message: 'Request could not be completed' });

    expect(normalizeApiError(cause, 'Request failed')).toStrictEqual({
      status: 400,
      message: 'Request could not be completed',
    });
  });

  it('falls back for malformed response data', () => {
    const cause = createAxiosError({ error: { message: 42 }, message: false }, 500);

    expect(normalizeApiError(cause, 'Unexpected server response')).toStrictEqual({
      status: 500,
      message: 'Unexpected server response',
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
    });
  });

  it('falls back for an Axios network error without a response', () => {
    const cause = new AxiosError('Network Error', AxiosError.ERR_NETWORK);

    expect(normalizeApiError(cause, 'Could not connect')).toStrictEqual({
      message: 'Could not connect',
    });
  });

  it('falls back for a non-Axios thrown value', () => {
    const cause = new Error('Unexpected failure');

    expect(normalizeApiError(cause, 'Something went wrong')).toStrictEqual({
      message: 'Something went wrong',
    });
  });
});
