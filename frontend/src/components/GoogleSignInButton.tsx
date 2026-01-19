import { useEffect, useRef } from 'react';
import config from '../config';
import { FcGoogle } from 'react-icons/fc';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: {
              type?: string;
              theme?: string;
              size?: string;
              text?: string;
              shape?: string;
              width?: number | string;
            }
          ) => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => void;
  onError: (error: string) => void;
}

export default function GoogleSignInButton({ onSuccess, onError }: GoogleSignInButtonProps) {
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!config.GOOGLE_CLIENT_ID) {
      return;
    }

    const initializeGoogle = () => {
      if (window.google && buttonRef.current) {
        window.google.accounts.id.initialize({
          client_id: config.GOOGLE_CLIENT_ID,
          callback: (response) => {
            if (response.credential) {
              onSuccess(response.credential);
            } else {
              onError('No credential received from Google');
            }
          },
        });

        // Render the button but make it invisible
        window.google.accounts.id.renderButton(buttonRef.current, {
          type: 'standard',
          theme: 'filled_black',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: 400, // Large width to ensure it covers the container
        });
      }
    };

    if (window.google) {
      initializeGoogle();
    } else {
      const checkGoogle = setInterval(() => {
        if (window.google) {
          clearInterval(checkGoogle);
          initializeGoogle();
        }
      }, 100);

      setTimeout(() => clearInterval(checkGoogle), 5000);
      return () => clearInterval(checkGoogle);
    }
  }, [onSuccess, onError]);

  if (!config.GOOGLE_CLIENT_ID) {
    return null;
  }

  return (
    <div className="relative w-full group cursor-pointer">
      {/* Custom Visual Button */}
      <div className="relative flex items-center justify-center gap-3 w-full rounded-xl bg-white/[0.05] border border-white/[0.1] px-4 py-3.5 transition-all duration-300 md:hover:bg-white/[0.08] md:hover:border-white/[0.2] md:hover:scale-[1.01] shadow-lg shadow-black/20">
        {/* Glow Effect */}
        <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-white/0 via-white/[0.05] to-white/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-sm" />
        
        <FcGoogle className="w-5 h-5 relative z-10" />
        <span className="text-sm font-medium text-white/90 relative z-10 tracking-wide">Continue with Google</span>
      </div>

      {/* Invisible Interactive Layer */}
      <div 
        ref={buttonRef} 
        className="absolute inset-0 opacity-0 z-20 overflow-hidden flex items-center justify-center [&>div]:w-full [&>div]:h-full [&>iframe]:scale-[1.5] [&>iframe]:opacity-0 cursor-pointer"
        aria-hidden="true"
      />
    </div>
  );
}
