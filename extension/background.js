// ── Background Service Worker ────────────────────────────────────────────────

const TOKEN_KEY = 'token';

// Listen for messages from the web app (externally_connectable)
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  // Verify the sender is our web app
  // The matches in manifest.json restrict who can send messages, but double checking URL is good practice
  const allowedOrigin = "https://vidwiz.online";
  const allowedDevOrigin = "http://localhost:5173"; 
  
  if (sender.url && (sender.url.startsWith(allowedOrigin) || sender.url.startsWith(allowedDevOrigin))) {
    
    if (message.type === 'SYNC_TOKEN') {
      const { token } = message;
      if (token) {
        chrome.storage.local.set({ [TOKEN_KEY]: token }, () => {
          console.log('Token synced from web app');
          sendResponse({ success: true });
        });
      } else {
        sendResponse({ success: false, error: 'No token provided' });
      }
    } else if (message.type === 'LOGOUT') {
      chrome.storage.local.remove(TOKEN_KEY, () => {
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
