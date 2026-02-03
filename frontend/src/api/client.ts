import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import config from '../config';
import { getToken, removeToken } from '../lib/authUtils';

const apiClient = axios.create({
  baseURL: config.API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add guest session ID if available
    const guestSessionId = sessionStorage.getItem('guestSessionId');
    if (guestSessionId) {
      config.headers['X-Guest-Session-ID'] = guestSessionId;
    }
    
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle common errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error: AxiosError) => {
    if (error.response) {
      // Handle 401 Unauthorized - clear token and potentially redirect
      if (error.response.status === 401) {
        removeToken();
        // Ideally we'd redirect here, but doing it in a plain JS file is tricky
        // without passing the router/navigate function.
        // Components should listen for 401s or check auth state.
        // Or we can emit an event.
        if (window.location.pathname !== '/login' && window.location.pathname !== '/signup') {
            window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
