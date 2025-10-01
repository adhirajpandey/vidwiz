
import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import vidwizLogo from '../public/vidwiz.png';
import config from '../config';

export default function SignupPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState(false);
  const { addToast } = useToast();
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
        title: 'Error',
        message: 'Passwords do not match',
        type: 'error',
      });
      return;
    }

    const validationError = validateFields();
    if (validationError) {
      addToast({
        title: 'Error',
        message: validationError,
        type: 'error',
      });
      return;
    }

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
          title: 'Success',
          message: 'Signup successful! You can now log in.',
          type: 'success',
        });
        navigate('/login');
      } else {
        addToast({
          title: 'Error',
          message: data.error || 'Something went wrong',
          type: 'error',
        });
      }
    } catch (error) {
      addToast({
        title: 'Error',
        message: 'Something went wrong',
        type: 'error',
      });
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 sm:px-8">
      <div className="w-full max-w-md space-y-8 rounded-2xl border border-border bg-card p-8 shadow-lg">
        <div className="text-center">
          <img src={vidwizLogo} alt="VidWiz" className="mx-auto h-12 w-auto" />
          <h2 className="mt-6 text-3xl font-bold tracking-tight text-foreground">
            Create a new account
          </h2>
        </div>
        <div className="space-y-6">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-muted-foreground"
            >
              Username
            </label>
            <div className="mt-1">
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="block w-full appearance-none rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder-muted-foreground shadow-sm focus:border-black focus:outline-none focus:ring-black sm:text-sm"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-muted-foreground"
            >
              Password
            </label>
            <div className="mt-1">
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full appearance-none rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder-muted-foreground shadow-sm focus:border-black focus:outline-none focus:ring-black sm:text-sm"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="confirm-password"
              className="block text-sm font-medium text-muted-foreground"
            >
              Confirm Password
            </label>
            <div className="mt-1">
              <input
                id="confirm-password"
                name="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`block w-full appearance-none rounded-md border ${passwordError ? 'border-red-500' : 'border-input'} bg-background px-3 py-2 text-foreground placeholder-muted-foreground shadow-sm focus:border-black focus:outline-none focus:ring-black sm:text-sm`}
              />
            </div>
          </div>

          <div>
            <button
              onClick={handleSignup}
              className="flex w-full justify-center rounded-md border border-transparent bg-red-500 py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 cursor-pointer"
            >
              Sign up
            </button>
          </div>
        </div>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-red-500 hover:text-red-600"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
