import { useEffect, useState } from 'react';
import { Check, X, AlertCircle } from 'lucide-react';

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
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    // Progress bar animation
    const duration = 4000;
    const interval = 50;
    const decrement = (interval / duration) * 100;
    
    const progressTimer = setInterval(() => {
      setProgress((prev) => Math.max(0, prev - decrement));
    }, interval);

    const closeTimer = setTimeout(() => {
      handleClose();
    }, duration);

    return () => {
      clearInterval(progressTimer);
      clearTimeout(closeTimer);
    };
  }, []);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      onClose(id);
    }, 200);
  };

  const typeConfig = {
    success: {
      icon: <Check className="w-4 h-4" strokeWidth={2.5} />,
      iconBg: 'bg-emerald-500',
      progressBar: 'bg-emerald-500',
      border: 'border-emerald-500/20',
    },
    error: {
      icon: <X className="w-4 h-4" strokeWidth={2.5} />,
      iconBg: 'bg-red-500',
      progressBar: 'bg-red-500',
      border: 'border-red-500/20',
    },
    info: {
      icon: <AlertCircle className="w-4 h-4" strokeWidth={2} />,
      iconBg: 'bg-blue-500',
      progressBar: 'bg-blue-500',
      border: 'border-blue-500/20',
    },
  };

  const config = typeConfig[type];

  return (
    <div
      className={`
        relative w-full overflow-hidden rounded-xl 
        bg-card/95 backdrop-blur-lg
        border ${config.border}
        shadow-lg shadow-black/10
        transition-all duration-200 ease-out
        ${isExiting 
          ? 'opacity-0 translate-x-4 scale-95' 
          : 'opacity-100 translate-x-0 scale-100'
        }
      `}
      role="alert"
    >
      <div className="flex items-start gap-3 p-4">
        {/* Icon */}
        <div className={`flex-shrink-0 w-6 h-6 rounded-full ${config.iconBg} flex items-center justify-center text-white`}>
          {config.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pt-0.5">
          <p className="text-sm font-medium text-foreground leading-tight">{title}</p>
          <p className="mt-0.5 text-[13px] text-muted-foreground leading-snug">{message}</p>
        </div>

        {/* Close Button */}
        <button
          onClick={handleClose}
          className="flex-shrink-0 w-6 h-6 -mt-0.5 -mr-0.5 rounded-md flex items-center justify-center text-foreground/40 hover:text-foreground hover:bg-foreground/5 transition-colors cursor-pointer"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Progress Bar */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-foreground/5">
        <div
          className={`h-full ${config.progressBar} transition-all duration-50 ease-linear`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
