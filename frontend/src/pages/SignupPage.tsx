
import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import vidwizLogo from '../public/vidwiz.png';
import config from '../config';
import { ArrowRight, User, Lock, Check, Sparkles } from 'lucide-react';
import AmbientBackground from '../components/ui/AmbientBackground';
import GlassCard from '../components/ui/GlassCard';
import GoogleSignInButton from '../components/GoogleSignInButton';

export default function SignupPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { addToast } = useToast();

  // Derived validation states
  const isPasswordValid = password.length > 6;
  const isUsernameValid = username.length > 4;
  const passwordsMatch = password === confirmPassword;
  const isFormValid = isUsernameValid && isPasswordValid && passwordsMatch && confirmPassword.length > 0;
  const navigate = useNavigate();

  useEffect(() => {
    if (password && confirmPassword && password !== confirmPassword) {
      setPasswordError(true);
    }
    else {
      setPasswordError(false);
    }
  }, [password, confirmPassword]);

  const validateFields = () => {
    if (username.length <= 4) {
      return 'Username must be greater than 4 characters';
    }
    if (password.length <= 6) {
      return 'Password must be greater than 6 characters';
    }
    return null;
  };

  const handleSignup = async () => {
    if (password !== confirmPassword) {
      addToast({
        title: 'Validation Error',
        message: 'Passwords do not match',
        type: 'error',
      });
      return;
    }

    const validationError = validateFields();
    if (validationError) {
      addToast({
        title: 'Validation Error',
        message: validationError,
        type: 'error',
      });
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${config.API_URL}/user/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        addToast({
          title: 'Account Created',
          message: 'Welcome to VidWiz! Please log in.',
          type: 'success',
        });
        navigate('/login');
      } else {
        addToast({
          title: 'Registration Failed',
          message: data.error || 'Something went wrong',
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
          message: 'Account created with Google',
          type: 'success',
        });
        navigate('/dashboard');
      } else {
        addToast({
          title: 'Sign-up Failed',
          message: data.error || 'Google sign-up failed',
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

      <div className="relative w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-700">
        
         {/* Value Prop Badge */}
         <div className="flex justify-center mb-6 select-none">
           <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 backdrop-blur-md">
             <Sparkles className="h-3.5 w-3.5 text-amber-400" />
             <span className="text-xs font-medium text-white/70">Join the community of smart learners</span>
           </div>
         </div>

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
              Create your account
            </h2>
            <p className="mt-2 text-sm text-white/50">
              Start your journey to better video learning
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
                  <span className="mx-4 text-xs text-white/30 select-none">or sign up with</span>
                  <div className="flex-grow border-t border-white/[0.08]"></div>
                </div>
              </>
            )}

            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="username" className="text-xs font-medium uppercase tracking-wider text-white/40 ml-1 select-none">
                  Username
                </label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-white/30 group-focus-within:text-red-400 transition-colors">
                    <User className="h-5 w-5" />
                  </div>
                  <input
                    id="username"
                    name="username"
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.03] pl-10 pr-3 py-3 text-white placeholder-white/20 focus:border-red-500/50 focus:bg-white/[0.05] focus:outline-none focus:ring-1 focus:ring-red-500/50 transition-all sm:text-sm"
                    placeholder="Choose a username"
                  />
                </div>
                {username && !isUsernameValid && (
                  <p className="text-xs text-amber-400 ml-1 mt-1 animate-in slide-in-from-top-1">Username must be more than 4 characters</p>
                )}
                {isUsernameValid && (
                  <p className="text-xs text-green-400 ml-1 mt-1 animate-in slide-in-from-top-1">✓ Username is valid</p>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-white/40 ml-1 select-none">
                  Password
                </label>
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
                    placeholder="Create a password"
                  />
                </div>
                {password && !isPasswordValid && (
                  <p className="text-xs text-amber-400 ml-1 mt-1 animate-in slide-in-from-top-1">Password must be more than 6 characters</p>
                )}
                {isPasswordValid && (
                  <p className="text-xs text-green-400 ml-1 mt-1 animate-in slide-in-from-top-1">✓ Password length is valid</p>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="confirm-password" className="text-xs font-medium uppercase tracking-wider text-white/40 ml-1 select-none">
                  Confirm Password
                </label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-white/30 group-focus-within:text-red-400 transition-colors">
                    <div className={`transition-colors ${passwordError ? 'text-red-500' : (isPasswordValid && passwordsMatch && confirmPassword ? 'text-green-500' : '')}`}>
                       {isPasswordValid && passwordsMatch && confirmPassword ? <Check className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
                    </div>
                  </div>
                  <input
                    id="confirm-password"
                    name="confirm-password"
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className={`block w-full rounded-xl border ${passwordError ? 'border-red-500/50' : 'border-white/[0.08]'} bg-white/[0.03] pl-10 pr-3 py-3 text-white placeholder-white/20 focus:border-red-500/50 focus:bg-white/[0.05] focus:outline-none focus:ring-1 focus:ring-red-500/50 transition-all sm:text-sm`}
                    placeholder="Repeat password"
                  />
                </div>
                {passwordError && (
                  <p className="text-xs text-red-400 ml-1 animate-in slide-in-from-top-1">Passwords do not match</p>
                )}
              </div>
            </div>

            <button
              onClick={handleSignup}
              disabled={isLoading || !isFormValid}
              className="group relative flex w-full justify-center items-center gap-2 rounded-xl bg-gradient-to-r from-red-600 to-red-500 py-3.5 px-4 text-sm font-semibold text-white shadow-lg shadow-red-500/20 hover:shadow-red-500/30 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer"
            >
              {isLoading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white"></div>
              ) : (
                <>
                  Create Account
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </button>


          </div>

          <div className="border-t border-white/[0.06] bg-white/[0.02] p-6 text-center select-none">
            <p className="text-sm text-white/40">
              Already have an account?{' '}
              <Link
                to="/login"
                className="font-medium text-red-400 hover:text-red-300 transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>
        </GlassCard>
        
        <div className="mt-8 text-center text-xs text-white/20 select-none">
          <p>© 2025 VidWiz. Secure registration.</p>
        </div>
      </div>
    </div>
  );
}
