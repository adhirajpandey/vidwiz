import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, X, AlertCircle } from 'lucide-react';

interface ToastProps {
  id: number;
  title: string;
  message: string;
  type: 'success' | 'error' | 'info';
  durationMs?: number;
  referenceId?: string;
  action?: { label: string; onClick: () => void };
  onClose: (id: number) => void;
}

export type { ToastProps };

export default function Toast({
  id,
  title,
  message,
  type,
  durationMs,
  referenceId,
  action,
  onClose,
}: ToastProps) {
  const [isExiting, setIsExiting] = useState(false);
  const [progress, setProgress] = useState(100);
  // The countdown pauses while the pointer is over the toast or focus is in it,
  // so its action and close button never expire mid-use.
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const duration = durationMs ?? (type === 'error' ? 6000 : 4000);
  const remaining = useRef(duration);

  const handleClose = useCallback(() => {
    setIsExiting(true);
    setTimeout(() => {
      onClose(id);
    }, 200);
  }, [id, onClose]);

  useEffect(() => {
    if (hovered || focused) return;
    const startedAt = Date.now();
    const startRemaining = remaining.current;
    const timer = setInterval(() => {
      remaining.current = Math.max(0, startRemaining - (Date.now() - startedAt));
      setProgress((remaining.current / duration) * 100);
      if (remaining.current === 0) {
        clearInterval(timer);
        handleClose();
      }
    }, 50);
    return () => clearInterval(timer);
  }, [duration, handleClose, hovered, focused]);

  const typeConfig = {
    success: {
      icon: <Check className="w-4 h-4" strokeWidth={2.5} />,
      iconBg: 'bg-success',
      progressBar: 'bg-success',
      border: 'border-border',
    },
    error: {
      icon: <X className="w-4 h-4" strokeWidth={2.5} />,
      iconBg: 'bg-destructive',
      progressBar: 'bg-destructive',
      border: 'border-destructive/30',
    },
    info: {
      icon: <AlertCircle className="w-4 h-4" strokeWidth={2} />,
      iconBg: 'bg-foreground',
      progressBar: 'bg-foreground',
      border: 'border-border',
    },
  };

  const config = typeConfig[type];

  return (
    <div
      className={`
        relative w-full overflow-hidden rounded-xl 
        bg-card
        border ${config.border}
        shadow-lg shadow-black/10
        transition-all duration-200 ease-out
        ${isExiting 
          ? 'opacity-0 translate-x-4 scale-95' 
          : 'opacity-100 translate-x-0 scale-100'
        }
      `}
      // Errors interrupt; confirmations and notes wait for a pause.
      role={type === 'error' ? 'alert' : 'status'}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); }}
    >
      <div className="flex items-start gap-3 p-4">
        {/* Icon */}
        <div className={`flex-shrink-0 w-6 h-6 rounded-full ${config.iconBg} flex items-center justify-center text-background`}>
          {config.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pt-0.5">
          <p className="text-sm font-medium text-foreground leading-tight">{title}</p>
          {message && <p className="mt-0.5 text-[13px] text-muted-foreground leading-snug">{message}</p>}
          {referenceId && (
            <p className="mt-1 text-[11px] font-mono text-muted-foreground/70 break-all">
              Reference: {referenceId}
            </p>
          )}
        </div>

        {action && (
          <button type="button" onClick={() => { action.onClick(); handleClose(); }} className="-my-0.5 inline-flex h-7 shrink-0 items-center rounded-[7px] bg-foreground px-2.5 text-xs font-semibold text-background hover:opacity-90">
            {action.label}
          </button>
        )}

        {/* Close Button */}
        <button
          onClick={handleClose}
          className="flex-shrink-0 w-6 h-6 -mt-0.5 -mr-0.5 rounded-md flex items-center justify-center text-foreground/40 hover:text-foreground hover:bg-foreground/5 transition-colors"
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
