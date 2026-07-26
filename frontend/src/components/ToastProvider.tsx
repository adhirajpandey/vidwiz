import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  ToastContext,
  type ToastContextType,
} from '../hooks/useToast';
import Toast, { type ToastProps } from './ui/Toast';

type ToastItem = Omit<ToastProps, 'onClose'>;
type ToastInput = Omit<ToastProps, 'id' | 'onClose'>;

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((toast: ToastInput) => {
    setToasts((currentToasts) => [
      ...currentToasts,
      { ...toast, id: Date.now() },
    ]);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((currentToasts) =>
      currentToasts.filter((toast) => toast.id !== id)
    );
  }, []);

  const contextValue = useMemo<ToastContextType>(
    () => ({ addToast }),
    [addToast]
  );

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div className="fixed top-4 right-4 z-[100] w-full max-w-[380px] pointer-events-none">
        <div className="flex flex-col gap-2.5 pointer-events-auto">
          {toasts.map((toast) => (
            <Toast key={toast.id} {...toast} onClose={removeToast} />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
