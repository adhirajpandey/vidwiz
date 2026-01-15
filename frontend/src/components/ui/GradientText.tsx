import type { FC, ReactNode } from 'react';

interface GradientTextProps {
  children: ReactNode;
  className?: string;
}

const GradientText: FC<GradientTextProps> = ({ children, className = '' }) => {
  return (
    <span className={`bg-gradient-to-r from-red-500 via-orange-500 to-red-500 bg-clip-text text-transparent bg-[length:200%_auto] animate-gradient ${className}`}>
      {children}
    </span>
  );
};

export default GradientText;
