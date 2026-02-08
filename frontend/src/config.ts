const configs = {
  development: {
    API_URL: 'https://api.vidwiz.online/v2',
    GOOGLE_CLIENT_ID: '265946502927-fsb0osc7ch7d9tvu4cr30oks5q4r61pt.apps.googleusercontent.com',
  },
  production: {
    API_URL: 'https://api.vidwiz.online/v2',
    GOOGLE_CLIENT_ID: '265946502927-fsb0osc7ch7d9tvu4cr30oks5q4r61pt.apps.googleusercontent.com',
  },
};

const config = import.meta.env.DEV ? configs.development : configs.production;

export default config;
