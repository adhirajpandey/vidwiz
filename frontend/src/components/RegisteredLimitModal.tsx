import React, { useState, useEffect } from 'react';
import { Lock, X, Timer } from 'lucide-react';

interface RegisteredLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
  resetInSeconds: number;
}

const RegisteredLimitModal: React.FC<RegisteredLimitModalProps> = ({ 
  isOpen, 
  onClose,
  resetInSeconds: initialResetSeconds 
}) => {
  const [timeLeft, setTimeLeft] = useState(initialResetSeconds);

  useEffect(() => {
    if (!isOpen || timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, timeLeft]);

  // Update local state if prop changes (e.g. reopened with new time)
  useEffect(() => {
    setTimeLeft(initialResetSeconds);
  }, [initialResetSeconds, isOpen]);

  if (!isOpen) return null;

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="relative w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl overflow-hidden scale-100 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Decorative background gradients */}
        <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-br from-indigo-600/20 via-blue-600/10 to-transparent pointer-events-none" />
        
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-muted/50 transition-colors z-10"
          aria-label="Close modal"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="relative p-6 sm:p-8 text-center">
          {/* Icon */}
          <div className="mx-auto mb-6 w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-blue-500/10 border border-indigo-500/20 flex items-center justify-center shadow-inner relative group">
            <div className="absolute inset-0 rounded-2xl bg-indigo-500/10 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <Lock className="w-8 h-8 text-indigo-500 relative z-10" />
          </div>

          <h3 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-foreground to-foreground/70 mb-3 px-4">
           Limit reached
          </h3>
          
          <div className="space-y-4 mb-8">
            <p className="text-lg font-medium text-foreground/90 leading-snug">
              Wow! You're really hitting it off with Wiz! <span className="inline-block animate-pulse">✨</span>
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              But our servers (and wallets) need a breather. We don't have enough resources to cater to your curiosity <span className="italic">just yet</span>.
            </p>
             <p className="text-sm text-muted-foreground leading-relaxed">
              Please wait a bit - turns out money doesn't actually grow on trees! 🌳💰
            </p>
          </div>

          {/* Timer Section */}
          <div className="bg-muted/30 border border-border rounded-xl p-4 mb-6">
            <div className="flex items-center justify-center gap-2 text-indigo-400 mb-1">
              <Timer className="w-4 h-4" />
              <span className="text-xs font-semibold uppercase tracking-wider">Unfreezes In</span>
            </div>
            <div className="text-3xl font-mono font-bold text-foreground">
              {formatTime(timeLeft)}
            </div>
          </div>

          <button
             onClick={onClose} 
             className="w-full rounded-xl bg-white/[0.05] border border-white/[0.1] px-4 py-3.5 transition-all duration-300 hover:bg-white/[0.08] hover:border-white/[0.2] text-sm font-medium text-foreground/90 tracking-wide"
          >
             Got it, I'll wait
          </button>
        </div>
      </div>
    </div>
  );
};

export default RegisteredLimitModal;
