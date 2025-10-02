
import { useEffect } from 'react';
import { CheckCircle, XCircle, X, Info } from 'lucide-react';

interface ToastProps {
  id: number;
  title: string;
  message: string;
  type: 'success' | 'error' | 'info';
  onClose: (id: number) => void;
}

export type { ToastProps };

export default function Toast({ id, title, message, type, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose(id);
    }, 5000);

    return () => {
      clearTimeout(timer);
    };
  }, [id, onClose]);

  const baseClasses = 'max-w-sm p-4 bg-card border rounded-lg shadow-lg';
  const typeClasses = {
    success: 'border-green-500',
    error: 'border-red-500',
    info: 'border-blue-500',
  };

  const ICONS = {
    success: <CheckCircle className="w-6 h-6 text-green-500" />,
    error: <XCircle className="w-6 h-6 text-red-500" />,
    info: <Info className="w-6 h-6 text-blue-500" />,
  };

  return (
    <div className={`${baseClasses} ${typeClasses[type]}`}>
      <div className="flex items-start">
        <div className="flex-shrink-0">{ICONS[type]}</div>
        <div className="ml-3 flex-1 pt-0.5">
          <p className="text-sm font-medium text-foreground">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{message}</p>
        </div>
        <div className="ml-4 flex-shrink-0 flex">
          <button
            onClick={() => onClose(id)}
            className="inline-flex text-muted-foreground bg-card rounded-md hover:text-foreground focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            <span className="sr-only">Close</span>
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
