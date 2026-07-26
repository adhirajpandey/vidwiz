import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import config from '../config';
import { getToken } from '../lib/authUtils';
import {
  markSessionExpiredHandled,
  notifySessionExpired,
  shouldNotifySessionExpired,
} from './session';

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
    if (
      error.response?.status === 401 &&
      shouldNotifySessionExpired(error.config?.url)
    ) {
      markSessionExpiredHandled(error);
      const requestId = error.response.headers?.['x-request-id'];
      notifySessionExpired({
        requestId: typeof requestId === 'string' ? requestId : undefined,
      });
    }
    return Promise.reject(error);
  }
);

export default apiClient;
