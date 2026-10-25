export interface ChromePort {
  postMessage(message: unknown): void;
  disconnect(): void;
  onMessage: { addListener(listener: (message: unknown) => void): void };
  onDisconnect: { addListener(listener: () => void): void };
}

declare global {
  interface Window {
    chrome?: typeof chrome;
  }

  const chrome: {
    runtime?: {
      lastError?: {
        message: string;
      };
      sendMessage?: (
        extensionId: string,
        message: unknown,
        responseCallback?: (...args: unknown[]) => void
      ) => void;
      connect?: (extensionId: string, options: { name: string }) => ChromePort;
    };
  };
}
