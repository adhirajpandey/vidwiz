import {
  Component,
  type ErrorInfo,
  type ReactNode,
} from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled frontend render error', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
        <div role="alert" className="w-full max-w-md text-center">
          <h1 className="text-xl font-semibold text-red-600 dark:text-red-400">
            Something went wrong
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            The page could not be displayed. Reload it, or return home and try
            again.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground cursor-pointer"
            >
              Reload page
            </button>
            <a
              href="/"
              className="rounded-lg bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
            >
              Go home
            </a>
          </div>
        </div>
      </main>
    );
  }
}
