import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, X, Info } from 'lucide-react';

interface ToastProps {
  id: number;
  title: string;
  message: string;
  type: 'success' | 'error' | 'info';
  onClose: (id: number) => void;
}

export type { ToastProps };

export default function Toast({ id, title, message, type, onClose }: ToastProps) {
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      handleClose();
    }, 5000);

    return () => {
      clearTimeout(timer);
    };
  }, []);

  const handleClose = () => {
    setIsExiting(true);
    // Wait for animation to finish before actually removing
    setTimeout(() => {
      onClose(id);
    }, 300);
  };

  const baseClasses = 'relative flex max-w-sm w-full overflow-hidden rounded-xl border p-4 shadow-2xl backdrop-blur-xl transition-all duration-300';
  
  // Animation classes
  const animationClasses = isExiting 
    ? 'animate-out fade-out slide-out-to-right-full' 
    : 'animate-in slide-in-from-right fade-in duration-300';

  const typeStyles = {
    success: {
      container: 'bg-black/80 border-green-500/20 shadow-green-500/10',
      iconBg: 'bg-green-500/10',
      iconColor: 'text-green-500',
      icon: <CheckCircle2 className="h-5 w-5" />,
      glow: 'bg-green-500'
    },
    error: {
      container: 'bg-black/80 border-red-500/20 shadow-red-500/10',
      iconBg: 'bg-red-500/10',
      iconColor: 'text-red-500',
      icon: <XCircle className="h-5 w-5" />,
      glow: 'bg-red-500'
    },
    info: {
      container: 'bg-black/80 border-blue-500/20 shadow-blue-500/10',
      iconBg: 'bg-blue-500/10',
      iconColor: 'text-blue-500',
      icon: <Info className="h-5 w-5" />,
      glow: 'bg-blue-500'
    },
  };

  const styles = typeStyles[type];

  return (
    <div className={`${baseClasses} ${styles.container} ${animationClasses}`} role="alert">
      {/* Ambient background glow */}
      <div className={`absolute -left-4 top-0 bottom-0 w-1 ${styles.glow} opacity-50`}></div>
      <div className={`absolute inset-0 bg-gradient-to-br from-white/[0.03] to-transparent pointer-events-none`}></div>

      <div className="relative flex w-full items-start gap-3">
        <div className={`flex-shrink-0 rounded-full p-1 ${styles.iconBg} ${styles.iconColor}`}>
          {styles.icon}
        </div>
        
        <div className="flex-1 pt-0.5">
          <p className="text-sm font-semibold text-white tracking-tight">{title}</p>
          <p className="mt-1 text-sm text-white/60 leading-relaxed">{message}</p>
        </div>

        <button
          onClick={handleClose}
          className="flex-shrink-0 -mr-1 -mt-1 rounded-lg p-1 text-white/40 hover:text-white hover:bg-white/10 transition-colors"
        >
          <span className="sr-only">Close</span>
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
