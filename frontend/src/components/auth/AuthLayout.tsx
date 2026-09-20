
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import vidwizLogo from '../../public/vidwiz.png';
import AmbientBackground from '../ui/AmbientBackground';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle: string;
  footer: ReactNode;
}

export default function AuthLayout({ children, title, subtitle, footer }: AuthLayoutProps) {
  return (
    <div className="auth-layout relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8">
      {/* Ambient Background Effects */}
      <AmbientBackground />

      <div className="relative w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-700">
        {/* Glass Card */}
        <div className="overflow-hidden rounded-3xl border border-border bg-card/95 text-card-foreground shadow-xl shadow-black/10 backdrop-blur-xl">
          {/* Header */}
          <div className="relative border-b border-border bg-muted/30 p-8 text-center select-none">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-500 to-transparent opacity-50"></div>
            <Link to="/" className="inline-block group">
              <div className="relative mx-auto mb-4 h-12 w-12 transition-transform duration-300 group-hover:scale-110">
                <div className="absolute inset-0 rounded-full bg-red-500/20 blur-md group-hover:bg-red-500/30"></div>
                <img src={vidwizLogo} alt="VidWiz" className="relative h-full w-full object-contain" />
              </div>
            </Link>
            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              {title}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {subtitle}
            </p>
          </div>

          <div className="p-8 space-y-6">
            {children}
          </div>

          <div className="border-t border-border bg-muted/30 p-6 text-center select-none">
            {footer}
          </div>
        </div>
      </div>
    </div>
  );
}
