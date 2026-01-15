import type { FC } from 'react';

interface AmbientBackgroundProps {
  className?: string;
}

const AmbientBackground: FC<AmbientBackgroundProps> = ({ className = '' }) => {
  return (
    <div className={`fixed inset-0 pointer-events-none ${className}`}>
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-violet-500/10 rounded-full blur-[120px] mix-blend-screen animate-pulse"></div>
      <div className="absolute top-[20%] right-[-10%] w-[35%] h-[40%] bg-red-500/10 rounded-full blur-[120px] mix-blend-screen animate-pulse" style={{ animationDelay: '2s' }}></div>
      <div className="absolute bottom-[-10%] left-[20%] w-[50%] h-[40%] bg-blue-500/10 rounded-full blur-[120px] mix-blend-screen animate-pulse" style={{ animationDelay: '4s' }}></div>
    </div>
  );
};

export default AmbientBackground;
