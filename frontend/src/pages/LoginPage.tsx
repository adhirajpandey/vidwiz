
import { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import config from '../config';
import { ArrowRight, Mail, Lock } from 'lucide-react';
import GoogleSignInButton from '../components/GoogleSignInButton';
import AuthLayout from '../components/auth/AuthLayout';
import { setToken } from '../lib/authUtils';
import { authApi } from '../api';
import {
  getValidationFieldErrors,
  normalizeApiError,
  toastApiError,
} from '../api/errors';
import Seo from '../components/Seo';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const { addToast } = useToast();
  const navigate = useNavigate();

  const handleLogin = async () => {
    setFieldErrors({});
    setIsLoading(true);
    try {
      const { token } = await authApi.login({ email, password });
      setToken(token);
      addToast({
        title: 'Welcome back!',
        message: 'Login successful',
        type: 'success',
      });
      navigate('/dashboard');
    } catch (error) {
      const nextFieldErrors = getValidationFieldErrors(normalizeApiError(error, 'Invalid credentials'));
      if (Object.keys(nextFieldErrors).length > 0) {
        setFieldErrors(nextFieldErrors);
        return;
      }
      toastApiError(addToast, error, 'Access Denied', 'Invalid credentials');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = useCallback(async (credential: string) => {
    setIsLoading(true);
    try {
      const { token } = await authApi.googleLogin({ credential });
      setToken(token);
      addToast({
        title: 'Welcome!',
        message: 'Google sign-in successful',
        type: 'success',
      });
      navigate('/dashboard');
    } catch (error) {
      toastApiError(addToast, error, 'Sign-in Failed', 'Google sign-in failed');
    } finally {
      setIsLoading(false);
    }
  }, [addToast, navigate]);

  const handleGoogleError = useCallback((error: string) => {
    addToast({
      title: 'Error',
      message: error,
      type: 'error',
    });
  }, [addToast]);

  return (
    <>
      <Seo
        title="Login: Continue with Smart Notes and Wiz | VidWiz"
        description="Welcome back to VidWiz. Sign in to access your Smart Notes, continue with Wiz, and manage your YouTube learning workflow."
        path="/login"
      />
      <AuthLayout
        title="Welcome back"
        subtitle="Sign in to continue to your dashboard"
        footer={
          <p className="text-sm text-muted-foreground">
            Don't have an account?{' '}
            <Link
              to="/signup"
              className="font-medium text-[var(--auth-error)] hover:text-[var(--auth-error)] transition-colors"
            >
              Sign up for free
            </Link>
          </p>
        }
      >
        {/* Google Sign In first */}
        {config.GOOGLE_CLIENT_ID && (
          <>
            <GoogleSignInButton
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
            />

            <div className="relative flex items-center">
              <div className="flex-grow border-t border-border"></div>
              <span className="mx-4 text-xs text-muted-foreground select-none">or continue with</span>
              <div className="flex-grow border-t border-border"></div>
            </div>
          </>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="email" className="text-xs font-medium uppercase tracking-wider text-muted-foreground ml-1 select-none">
              Email
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted-foreground group-focus-within:text-[var(--auth-error)] transition-colors">
                <Mail className="h-5 w-5" />
              </div>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setFieldErrors((current) => ({ ...current, email: '' }));
                }}
                aria-invalid={Boolean(fieldErrors.email)}
                aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
                className="block w-full rounded-xl border border-border bg-background pl-10 pr-3 py-3 text-foreground placeholder:text-muted-foreground focus:border-red-500/50 focus:bg-muted/40 focus:outline-none focus:ring-1 focus:ring-red-500/50 transition-all sm:text-sm"
                placeholder="Enter your email"
              />
            </div>
            {fieldErrors.email && (
              <p id="login-email-error" className="ml-1 text-xs text-[var(--auth-error)]">
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center ml-1">
              <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-muted-foreground select-none">
                Password
              </label>
            </div>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted-foreground group-focus-within:text-[var(--auth-error)] transition-colors">
                <Lock className="h-5 w-5" />
              </div>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setFieldErrors((current) => ({ ...current, password: '' }));
                }}
                aria-invalid={Boolean(fieldErrors.password)}
                aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
                className="block w-full rounded-xl border border-border bg-background pl-10 pr-3 py-3 text-foreground placeholder:text-muted-foreground focus:border-red-500/50 focus:bg-muted/40 focus:outline-none focus:ring-1 focus:ring-red-500/50 transition-all sm:text-sm"
                placeholder="••••••••"
              />
            </div>
            {fieldErrors.password && (
              <p id="login-password-error" className="ml-1 text-xs text-[var(--auth-error)]">
                {fieldErrors.password}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={handleLogin}
          disabled={isLoading}
          className="group relative flex w-full justify-center items-center gap-2 rounded-xl bg-gradient-to-r from-red-600 to-red-500 py-3.5 px-4 text-sm font-semibold text-white shadow-lg shadow-red-500/20 hover:shadow-red-500/30 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer"
        >
          {isLoading ? (
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white"></div>
          ) : (
            <>
              Sign in
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </>
          )}
        </button>
      </AuthLayout>
    </>
  );
}
