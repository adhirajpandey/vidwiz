import { useEffect, useRef, useState } from 'react';
import config from '../config';

function GoogleLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

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
  const [isReady, setIsReady] = useState(false);

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
        
        // Mark as ready once rendered
        setIsReady(true);
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
    <div className="relative w-full group cursor-pointer focus-within:ring-2 focus-within:ring-accent rounded-lg">
      {/* Visible button; Google's own button sits invisibly on top to receive the click. */}
      <div
        className={`relative flex h-10 items-center justify-center gap-3 w-full rounded-lg border border-border bg-card px-4 transition-colors group-hover:bg-muted ${!isReady ? 'opacity-80 cursor-wait' : ''}`}
      >

        {isReady ? (
          <>
            <GoogleLogo className="size-4" />
            <span className="text-sm font-medium text-foreground">Continue with Google</span>
          </>
        ) : (
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-foreground"></div>
            <span className="text-sm font-medium text-muted-foreground">Loading...</span>
          </div>
        )}
      </div>

      {/* Invisible Interactive Layer - only present when ready */}
      <div 
        ref={buttonRef} 
        className={`absolute inset-0 z-20 overflow-hidden flex items-center justify-center [&>div]:w-full [&>div]:h-full [&>iframe]:scale-[1.1] ${isReady ? 'opacity-[0.01]' : 'hidden'}`}
        aria-hidden="true"
      />
    </div>
  );
}
