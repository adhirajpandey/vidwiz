const configs = {
  development: {
    API_URL: 'https://api.vidwiz.online/v2',
    GOOGLE_CLIENT_ID: '265946502927-fsb0osc7ch7d9tvu4cr30oks5q4r61pt.apps.googleusercontent.com',
    EXTENSION_ID: 'jmkflagepabkiopnlbdfdflcpnfiahmf',
  },
  production: {
    API_URL: 'https://api.vidwiz.online/v2',
    GOOGLE_CLIENT_ID: '265946502927-fsb0osc7ch7d9tvu4cr30oks5q4r61pt.apps.googleusercontent.com',
    EXTENSION_ID: 'YOUR_EXTENSION_ID_HERE', // TODO: user to replace this
  },
};

const config = import.meta.env.DEV ? configs.development : configs.production;

export default config;
