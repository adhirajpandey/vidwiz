const CONSTANTS = {
  STORAGE: {
    TOKEN: "token"
  },
  MESSAGES: {
    SYNC_TOKEN: "SYNC_TOKEN",
    LOGOUT: "LOGOUT"
  },
  ORIGINS: {
    PROD: "https://vidwiz.online"
  }
};

// Listen for messages from the web app (externally_connectable)
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  // externally_connectable already restricts senders; also require an exact origin match.
  if (sender.origin === CONSTANTS.ORIGINS.PROD) {
    
    if (message.type === CONSTANTS.MESSAGES.SYNC_TOKEN) {
      const { token } = message;
      if (token) {
        chrome.storage.local.set({ [CONSTANTS.STORAGE.TOKEN]: token }, () => {
          console.log('Token synced from web app');
          sendResponse({ success: true });
        });
      } else {
        sendResponse({ success: false, error: 'No token provided' });
      }
    } else if (message.type === CONSTANTS.MESSAGES.LOGOUT) {
      chrome.storage.local.remove(CONSTANTS.STORAGE.TOKEN, () => {
        console.log('Token removed (logout)');
        sendResponse({ success: true });
      });
    } else {
      sendResponse({ success: false, error: 'Unknown message type' });
    }
    
    // Return true to indicate we wish to send a response asynchronously
    return true; 
  }
});
