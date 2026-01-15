import type { FC, ReactNode } from 'react';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hoverEffect?: boolean;
}

const GlassCard: FC<GlassCardProps> = ({ children, className = '', hoverEffect = false }) => {
  const hoverClasses = hoverEffect 
    ? 'hover:bg-white/[0.04] hover:border-white/[0.12] transition-all duration-300' 
    : '';

  return (
    <div className={`backdrop-blur-xl bg-black/40 border border-white/[0.08] shadow-2xl ${hoverClasses} ${className}`}>
      {children}
    </div>
  );
};

export default GlassCard;
