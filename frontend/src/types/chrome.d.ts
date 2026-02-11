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
    };
  };
}

export {};
