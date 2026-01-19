import { useEffect, useRef } from 'react';
import config from '../config';

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
              width?: number;
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

        window.google.accounts.id.renderButton(buttonRef.current, {
          type: 'standard',
          theme: 'filled_black',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: 320,
        });
      }
    };

    // Check if Google script is already loaded
    if (window.google) {
      initializeGoogle();
    } else {
      // Wait for script to load
      const checkGoogle = setInterval(() => {
        if (window.google) {
          clearInterval(checkGoogle);
          initializeGoogle();
        }
      }, 100);

      // Cleanup after 5 seconds if not loaded
      setTimeout(() => clearInterval(checkGoogle), 5000);

      return () => clearInterval(checkGoogle);
    }
  }, [onSuccess, onError]);

  if (!config.GOOGLE_CLIENT_ID) {
    return null;
  }

  return (
    <div className="flex justify-center">
      <div ref={buttonRef} />
    </div>
  );
}
