import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import vidwizLogo from '../public/vidwiz.png';
import config from '../config';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { addToast } = useToast();
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      const response = await fetch(`${config.API_URL}/user/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('token', data.token);
        addToast({
          title: 'Success',
          message: 'Login successful!',
          type: 'success',
        });
        navigate('/dashboard');
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
            Sign in to your account
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
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full appearance-none rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder-muted-foreground shadow-sm focus:border-black focus:outline-none focus:ring-black sm:text-sm"
              />
            </div>
          </div>

          <div>
            <button
              onClick={handleLogin}
              className="flex w-full justify-center rounded-md border border-transparent bg-red-500 py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 cursor-pointer"
            >
              Sign in
            </button>
          </div>
        </div>
        <p className="text-center text-sm text-muted-foreground">
          Don't have an account?{' '}
          <Link
            to="/signup"
            className="font-medium text-red-500 hover:text-red-600"
          >
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
