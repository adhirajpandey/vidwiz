
import { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import config from '../config';
import { ArrowRight, Mail, Lock } from 'lucide-react';
import GoogleSignInButton from '../components/GoogleSignInButton';
import AuthLayout from '../components/auth/AuthLayout';
import { setToken } from '../lib/authUtils';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { addToast } = useToast();
  const navigate = useNavigate();

  const handleLogin = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${config.API_URL}/user/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        setToken(data.token);
        addToast({
          title: 'Welcome back!',
          message: 'Login successful',
          type: 'success',
        });
        navigate('/dashboard');
      } else {
        addToast({
          title: 'Access Denied',
          message: data.error || 'Invalid credentials',
          type: 'error',
        });
      }
    } catch (error) {
      addToast({
        title: 'Connection Error',
        message: 'Could not connect to server',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = useCallback(async (credential: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${config.API_URL}/user/google/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ credential }),
      });

      const data = await response.json();

      if (response.ok) {
        setToken(data.token);
        addToast({
          title: 'Welcome!',
          message: 'Google sign-in successful',
          type: 'success',
        });
        navigate('/dashboard');
      } else {
        addToast({
          title: 'Sign-in Failed',
          message: data.error || 'Google sign-in failed',
          type: 'error',
        });
      }
    } catch (error) {
      addToast({
        title: 'Connection Error',
        message: 'Could not connect to server',
        type: 'error',
      });
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
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your dashboard"
      footer={
        <p className="text-sm text-white/40">
          Don't have an account?{' '}
          <Link
            to="/signup"
            className="font-medium text-red-400 hover:text-red-300 transition-colors"
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
            <div className="flex-grow border-t border-white/[0.08]"></div>
            <span className="mx-4 text-xs text-white/30 select-none">or continue with</span>
            <div className="flex-grow border-t border-white/[0.08]"></div>
          </div>
        </>
      )}

      <div className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="email" className="text-xs font-medium uppercase tracking-wider text-white/40 ml-1 select-none">
            Email
          </label>
          <div className="relative group">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-white/30 group-focus-within:text-red-400 transition-colors">
              <Mail className="h-5 w-5" />
            </div>
            <input
              id="email"
              name="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.03] pl-10 pr-3 py-3 text-white placeholder-white/20 focus:border-red-500/50 focus:bg-white/[0.05] focus:outline-none focus:ring-1 focus:ring-red-500/50 transition-all sm:text-sm"
              placeholder="Enter your email"
            />
          </div>
        </div>


        <div className="space-y-2">
          <div className="flex justify-between items-center ml-1">
            <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-white/40 select-none">
              Password
            </label>
          </div>
          <div className="relative group">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-white/30 group-focus-within:text-red-400 transition-colors">
              <Lock className="h-5 w-5" />
            </div>
            <input
              id="password"
              name="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.03] pl-10 pr-3 py-3 text-white placeholder-white/20 focus:border-red-500/50 focus:bg-white/[0.05] focus:outline-none focus:ring-1 focus:ring-red-500/50 transition-all sm:text-sm"
              placeholder="••••••••"
            />
          </div>
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
  );
}
