
import { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import vidwizLogo from '../public/vidwiz.png';
import config from '../config';
import { ArrowRight, Mail, Lock } from 'lucide-react';
import AmbientBackground from '../components/ui/AmbientBackground';
import GlassCard from '../components/ui/GlassCard';
import GoogleSignInButton from '../components/GoogleSignInButton';

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
        localStorage.setItem('token', data.token);
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
        localStorage.setItem('token', data.token);
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 sm:px-6">
      {/* Ambient Background Effects */}
      <AmbientBackground />

      <div className="relative w-full max-w-md animate-in fade-in zoom-in-95 duration-500">
        {/* Glass Card */}
        <GlassCard className="overflow-hidden rounded-3xl shadow-2xl">
          {/* Header */}
          <div className="relative border-b border-white/[0.06] bg-white/[0.02] p-8 text-center select-none">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-500 to-transparent opacity-50"></div>
            <Link to="/" className="inline-block group">
              <div className="relative mx-auto mb-4 h-12 w-12 transition-transform duration-300 group-hover:scale-110">
                <div className="absolute inset-0 rounded-full bg-red-500/20 blur-md group-hover:bg-red-500/30"></div>
                <img src={vidwizLogo} alt="VidWiz" className="relative h-full w-full object-contain" />
              </div>
            </Link>
            <h2 className="text-2xl font-bold tracking-tight text-white">
              Welcome back
            </h2>
            <p className="mt-2 text-sm text-white/50">
              Sign in to continue to your dashboard
            </p>
          </div>

          <div className="p-8 space-y-6">
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


          </div>

          <div className="border-t border-white/[0.06] bg-white/[0.02] p-6 text-center select-none">
            <p className="text-sm text-white/40">
              Don't have an account?{' '}
              <Link
                to="/signup"
                className="font-medium text-red-400 hover:text-red-300 transition-colors"
              >
                Sign up for free
              </Link>
            </p>
          </div>
        </GlassCard>
        
        <div className="mt-8 text-center text-xs text-white/20 select-none">
          <p>© 2025 VidWiz. Secure login.</p>
        </div>
      </div>
    </div>
  );
}
