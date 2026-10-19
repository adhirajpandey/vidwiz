import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { authApi, getValidationFieldErrors, normalizeApiError } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { setToken } from '../../lib/authUtils';
import Seo from '../../components/Seo';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import AuthCard from './AuthCard';
import { useAfterSignIn } from './useAfterSignIn';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const notify = useNotify();
  const done = useAfterSignIn();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setErrors({});
    setLoading(true);
    try {
      const { token } = await authApi.login({ email, password });
      setToken(token);
      done();
    } catch (cause) {
      const fields = getValidationFieldErrors(normalizeApiError(cause, 'Invalid email or password.'));
      if (Object.keys(fields).length) setErrors(fields);
      else notify.error(cause, 'Sign-in failed', 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Seo title="Log in | VidWiz" description="Log in to VidWiz to search and ask across the YouTube moments you saved." path="/login" />
      <AuthCard
        title="Welcome back"
        subtitle="Log in to your library"
        footer={<>New to VidWiz? <Link to="/signup" className="font-medium text-accent hover:underline">Create an account</Link></>}
      >
        <form onSubmit={submit} className="space-y-3" noValidate>
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium">Email</label>
            <Input id="email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} aria-invalid={Boolean(errors.email)} required />
            {errors.email && <p className="text-xs text-destructive">{errors.email}</p>}
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} aria-invalid={Boolean(errors.password)} required />
            {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
          </div>
          <Button type="submit" variant="primary" className="w-full justify-center" disabled={loading || !email || !password}>
            {loading ? 'Logging in…' : 'Log in'}
          </Button>
        </form>
      </AuthCard>
    </>
  );
}
