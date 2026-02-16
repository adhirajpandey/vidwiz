const PRICING = [
  { credits: 200, price: 20, perCredit: 0.10 },
  { credits: 600, price: 50, perCredit: 0.083 },
  { credits: 1500, price: 100, perCredit: 0.067 },
];

const configs = {
  development: {
    API_URL: 'https://api.vidwiz.online/v2',
    GOOGLE_CLIENT_ID: '265946502927-fsb0osc7ch7d9tvu4cr30oks5q4r61pt.apps.googleusercontent.com',
    EXTENSION_ID: 'jmkflagepabkiopnlbdfdflcpnfiahmf',
  },
  production: {
    API_URL: 'https://api.vidwiz.online/v2',
    GOOGLE_CLIENT_ID: '265946502927-fsb0osc7ch7d9tvu4cr30oks5q4r61pt.apps.googleusercontent.com',
    EXTENSION_ID: 'bgiahikcnhdljbfeknfbfpdnbnkpjiop',
  },
};

const envConfig = import.meta.env.DEV ? configs.development : configs.production;

const config = {
  ...envConfig,
  CHROME_WEBSTORE_URL: 'https://chromewebstore.google.com/detail/vidwiz/bgiahikcnhdljbfeknfbfpdnbnkpjiop',
  SIGNUP_CREDITS: 100,
  NOTES_POLL_INTERVAL_MS: 4000,
  PRICING,
};

export default config;
