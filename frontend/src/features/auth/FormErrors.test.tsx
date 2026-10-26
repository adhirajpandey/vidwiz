// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HelmetProvider } from 'react-helmet-async';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { ApiError, authApi } from '../../api';
import LoginPage from './LoginPage';
import SignupPage from './SignupPage';
import AddVideoForm from '../library/AddVideoForm';

vi.mock('./AuthCard', () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));
vi.mock('../../hooks/useNotify', () => ({ useNotify: () => ({ error: vi.fn() }) }));
vi.mock('../../api', async original => ({ ...await original<typeof import('../../api')>(), authApi: { login: vi.fn(), register: vi.fn() } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function setup(children: ReactNode) {
  render(<HelmetProvider><QueryClientProvider client={new QueryClient()}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider></HelmetProvider>);
}
function check(input: HTMLElement, message: string) {
  expect(input.getAttribute('aria-invalid')).toBe('true');
  expect(document.getElementById(input.getAttribute('aria-describedby')!)?.textContent).toBe(message);
}
it('associates a login server validation error with the email field', async () => {
  vi.mocked(authApi.login).mockRejectedValue(new ApiError(new Response(null, { status: 422 }), { error: { message: 'Invalid email', details: [{ field: 'email', message: 'Enter a valid email.' }] } }));
  setup(<LoginPage />);
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'invalid' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }));
  await screen.findByText('Enter a valid email.');
  check(screen.getByLabelText('Email'), 'Enter a valid email.');
  expect(screen.getByLabelText('Password').getAttribute('aria-describedby')).toBeNull();
});
it('associates the signup password length error with its field', () => {
  setup(<SignupPage />);
  for (const [name, value] of [['Name', 'Someone'], ['Email', 'someone@example.com'], ['Password', 'short']]) fireEvent.change(screen.getByLabelText(name), { target: { value } });
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  check(screen.getByLabelText('Password'), 'Use at least 8 characters.');
  expect(authApi.register).not.toHaveBeenCalled();
});
it('associates add-video validation with the link field', () => {
  setup(<AddVideoForm />);
  const input = screen.getByRole('textbox', { name: 'YouTube link' });
  fireEvent.change(input, { target: { value: 'invalid' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add' }));
  check(input, 'Paste a YouTube video link, like youtube.com/watch?v=… or youtu.be/…');
});
