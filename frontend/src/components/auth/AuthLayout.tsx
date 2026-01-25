
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import vidwizLogo from '../../public/vidwiz.png';
import AmbientBackground from '../ui/AmbientBackground';
import GlassCard from '../ui/GlassCard';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle: string;
  footer: ReactNode;
}

export default function AuthLayout({ children, title, subtitle, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8">
      {/* Ambient Background Effects */}
      <AmbientBackground />

      <div className="relative w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-700">
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
              {title}
            </h2>
            <p className="mt-2 text-sm text-white/50">
              {subtitle}
            </p>
          </div>

          <div className="p-8 space-y-6">
            {children}
          </div>

          <div className="border-t border-white/[0.06] bg-white/[0.02] p-6 text-center select-none">
            {footer}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
