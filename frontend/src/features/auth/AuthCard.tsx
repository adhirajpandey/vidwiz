import { useCallback } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import { setToken } from '../../lib/authUtils';
import GoogleSignInButton from '../../components/GoogleSignInButton';
import { useAfterSignIn } from './useAfterSignIn';

export default function AuthCard({ title, subtitle, children, footer }: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  const notify = useNotify();
  const done = useAfterSignIn();
  const google = useCallback(async (credential: string) => {
    try {
      const { token } = await authApi.googleLogin({ credential });
      setToken(token);
      done();
    } catch (cause) {
      notify.error(cause, 'Sign-in failed', 'Google sign-in failed.');
    }
  }, [done, notify]);
  const googleError = useCallback((message: string) => notify.error(new Error(message), 'Sign-in failed', message), [notify]);

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 py-10">
      <div className="text-center">
        <Link to="/" className="mx-auto mb-5 block w-fit"><img src="/icon-192.png" alt="VidWiz" className="size-10 rounded-lg" /></Link>
        <h1 className="display text-3xl">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <div className="space-y-4 rounded-[14px] border border-border bg-card p-6">
        {config.GOOGLE_CLIENT_ID && (
          <>
            <GoogleSignInButton onSuccess={google} onError={googleError} />
            <div className="flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or with email<span className="h-px flex-1 bg-border" /></div>
          </>
        )}
        {children}
      </div>
      <p className="text-center text-sm text-muted-foreground">{footer}</p>
    </div>
  );
}
