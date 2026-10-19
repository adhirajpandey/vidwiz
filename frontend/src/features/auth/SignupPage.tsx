import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { authApi, getValidationFieldErrors, normalizeApiError } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import { setToken } from '../../lib/authUtils';
import Seo from '../../components/Seo';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import AuthCard from './AuthCard';
import { useAfterSignIn } from './useAfterSignIn';

export default function SignupPage() {
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const notify = useNotify();
  const done = useAfterSignIn();
  const set = (key: keyof typeof form) => (value: string) => setForm(previous => ({ ...previous, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (form.password.length < 8) {
      setErrors({ password: 'Use at least 8 characters.' });
      return;
    }
    setErrors({});
    setLoading(true);
    try {
      await authApi.register(form);
      const { token } = await authApi.login({ email: form.email, password: form.password });
      setToken(token);
      done();
    } catch (cause) {
      const fields = getValidationFieldErrors(normalizeApiError(cause, 'The account could not be created.'));
      if (Object.keys(fields).length) setErrors(fields);
      else notify.error(cause, 'Sign-up failed', 'The account could not be created.');
    } finally {
      setLoading(false);
    }
  };

  const field = (key: keyof typeof form, label: string, type: string, autoComplete: string) => (
    <div className="space-y-1">
      <label htmlFor={key} className="text-sm font-medium">{label}</label>
      <Input id={key} type={type} autoComplete={autoComplete} value={form[key]} onChange={event => set(key)(event.target.value)} aria-invalid={Boolean(errors[key])} required />
      {errors[key] && <p className="text-xs text-destructive">{errors[key]}</p>}
    </div>
  );

  return (
    <>
      <Seo title="Sign up | VidWiz" description="Create a VidWiz account to capture YouTube moments and find them again." path="/signup" />
      <AuthCard
        title="Create your account"
        subtitle={`Start with ${config.SIGNUP_CREDITS} free credits`}
        footer={<>Already have an account? <Link to="/login" className="font-medium text-accent hover:underline">Log in</Link></>}
      >
        <form onSubmit={submit} className="space-y-3" noValidate>
          {field('name', 'Name', 'text', 'name')}
          {field('email', 'Email', 'email', 'email')}
          {field('password', 'Password', 'password', 'new-password')}
          <Button type="submit" variant="primary" className="w-full justify-center" disabled={loading || !form.name || !form.email || !form.password}>
            {loading ? 'Creating account…' : 'Create account'}
          </Button>
        </form>
      </AuthCard>
    </>
  );
}
