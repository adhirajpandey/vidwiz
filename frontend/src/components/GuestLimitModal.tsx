import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, X, Mail } from 'lucide-react';
import GoogleSignInButton from './GoogleSignInButton';
import { useToast } from '../hooks/useToast';
import config from '../config';

interface GuestLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const GuestLimitModal: React.FC<GuestLimitModalProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleGoogleSuccess = async (credential: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${config.API_URL}/user/google/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ credential }),
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('token', data.token);
        addToast({
          title: 'Welcome!',
          message: 'Signed in successfully',
          type: 'success',
        });
        // Reload the page to refresh context with the new token
        window.location.reload();
      } else {
        addToast({
          title: 'Sign-in Failed',
          message: data.error || 'Google sign-in failed',
          type: 'error',
        });
        setIsLoading(false);
      }
    } catch (error) {
      addToast({
        title: 'Connection Error',
        message: 'Could not connect to server',
        type: 'error',
      });
      setIsLoading(false);
    }
  };

  const handleGoogleError = (error: string) => {
    addToast({
      title: 'Error',
      message: error,
      type: 'error',
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="relative w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl overflow-hidden scale-100 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Decorative background gradients */}
        <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-br from-violet-600/20 via-fuchsia-600/10 to-transparent pointer-events-none" />
        
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
          <div className="mx-auto mb-6 w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20 flex items-center justify-center shadow-inner relative group">
            <div className="absolute inset-0 rounded-2xl bg-violet-500/10 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <Lock className="w-8 h-8 text-violet-500 relative z-10" />
          </div>

          <h3 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-foreground to-foreground/70 mb-3 px-4">
            Trial limit reached
          </h3>
          
          <div className="space-y-4 mb-8">
            <p className="text-lg font-medium text-foreground/90">
              You and Wiz are really hitting it off!
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed max-w-xs mx-auto">
              Don't let the learning stop here. Create a free account to unlock <span className="text-violet-500 font-medium">more features</span>.
            </p>
          </div>

          <div className="space-y-4">
            {/* Google Button */}
             {isLoading ? (
                <div className="flex items-center justify-center gap-2 w-full rounded-xl bg-muted/20 border border-border px-4 py-3.5">
                   <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent"></div>
                   <span className="text-sm font-medium text-foreground/70">Signing in...</span>
                </div>
             ) : (
                <GoogleSignInButton
                   onSuccess={handleGoogleSuccess}
                   onError={handleGoogleError}
                />
             )}

            <div className="relative flex items-center py-2">
              <div className="flex-grow border-t border-border"></div>
              <span className="mx-4 text-[10px] uppercase tracking-wider text-muted-foreground/60 select-none">OR</span>
              <div className="flex-grow border-t border-border"></div>
            </div>

            <button
               onClick={() => navigate('/signup')} 
               className="relative flex items-center justify-center gap-3 w-full rounded-xl bg-white/[0.05] border border-white/[0.1] px-4 py-3.5 transition-all duration-300 md:hover:bg-white/[0.08] md:hover:border-white/[0.2] md:hover:scale-[1.01] shadow-lg shadow-black/20 group cursor-pointer"
            >
               <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-white/0 via-white/[0.05] to-white/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-sm" />
               <Mail className="w-5 h-5 relative z-10 text-foreground/90" />
               <span className="text-sm font-medium text-foreground/90 relative z-10 tracking-wide">Continue with Email</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GuestLimitModal;
