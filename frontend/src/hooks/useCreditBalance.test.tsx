// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '../api';
import { useCreditBalance } from './useCreditBalance';

vi.mock('../api', () => ({ authApi: { getMe: vi.fn() } }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const profile = (credits_balance: number) => ({ credits_balance });

beforeEach(() => vi.resetAllMocks());
afterEach(cleanup);

describe('useCreditBalance', () => {
  it.each([0, 1_234_567])('loads a balance of %s when enabled', async balance => {
    vi.mocked(authApi.getMe).mockResolvedValue(profile(balance) as never);
    const hook = renderHook(() => useCreditBalance(true, 'user@example.com'));
    expect(hook.result.current.status).toBe('loading');
    await waitFor(() => expect(hook.result.current).toMatchObject({ status: 'success', balance }));
  });

  it('does not fetch for a guest', () => {
    renderHook(() => useCreditBalance(false, null));
    expect(authApi.getMe).not.toHaveBeenCalled();
  });

  it('reports failures and retries', async () => {
    vi.mocked(authApi.getMe)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(profile(42) as never);
    const hook = renderHook(() => useCreditBalance(true, 'user@example.com'));
    await waitFor(() => expect(hook.result.current.status).toBe('error'));
    await act(async () => hook.result.current.retry());
    expect(hook.result.current).toMatchObject({ status: 'success', balance: 42 });
  });

  it('refreshes after reopening and when the window regains focus', async () => {
    vi.mocked(authApi.getMe)
      .mockResolvedValueOnce(profile(10) as never)
      .mockResolvedValueOnce(profile(20) as never)
      .mockResolvedValueOnce(profile(30) as never);
    const hook = renderHook(({ enabled }) => useCreditBalance(enabled, 'user@example.com'), {
      initialProps: { enabled: true },
    });
    await waitFor(() => expect(hook.result.current.balance).toBe(10));
    hook.rerender({ enabled: false });
    hook.rerender({ enabled: true });
    await waitFor(() => expect(hook.result.current.balance).toBe(20));
    act(() => window.dispatchEvent(new Event('focus')));
    await waitFor(() => expect(hook.result.current.balance).toBe(30));
  });

  it('ignores obsolete responses after close, account change, and a newer request', async () => {
    const first = deferred<ReturnType<typeof profile>>();
    const second = deferred<ReturnType<typeof profile>>();
    const third = deferred<ReturnType<typeof profile>>();
    vi.mocked(authApi.getMe)
      .mockReturnValueOnce(first.promise as never)
      .mockReturnValueOnce(second.promise as never)
      .mockReturnValueOnce(third.promise as never);
    const hook = renderHook(({ enabled, account }) => useCreditBalance(enabled, account), {
      initialProps: { enabled: true, account: 'first@example.com' as string | null },
    });
    hook.rerender({ enabled: false, account: null });
    await act(async () => first.resolve(profile(5)));
    expect(hook.result.current.status).toBe('idle');

    hook.rerender({ enabled: true, account: 'second@example.com' });
    act(() => window.dispatchEvent(new Event('focus')));
    await act(async () => third.resolve(profile(30)));
    await waitFor(() => expect(hook.result.current.balance).toBe(30));
    await act(async () => second.resolve(profile(20)));
    expect(hook.result.current.balance).toBe(30);
  });
});
