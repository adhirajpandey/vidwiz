import apiClient from './client';
import type {
  TokenResponse,
  TokenRevokeResponse,
  UserProfileRead,
  MessageResponse,
} from './types';

// Define payloads locally as they were before
export interface AuthLoginPayload {
  email: string;
  password: string;
}

export interface AuthRegisterPayload {
  email: string;
  name: string;
  password: string;
}

export interface GoogleLoginPayload {
  credential: string;
}

export interface UserProfileUpdatePayload {
  name?: string;
  ai_notes_enabled?: boolean;
}

// Response types based on backend schemas
export interface AuthResponse {
  token: string;
}

export const authApi = {
  login: async (payload: AuthLoginPayload) => {
    const response = await apiClient.post<AuthResponse>('/auth/login', payload);
    return response.data;
  },

  register: async (payload: AuthRegisterPayload) => {
    const response = await apiClient.post<MessageResponse>('/auth/register', payload);
    return response.data;
  },

  googleLogin: async (payload: GoogleLoginPayload) => {
    const response = await apiClient.post<AuthResponse>('/auth/google', payload);
    return response.data;
  },

  getMe: async () => {
    const response = await apiClient.get<UserProfileRead>('/users/me');
    return response.data;
  },

  updateProfile: async (payload: UserProfileUpdatePayload) => {
    const response = await apiClient.patch<UserProfileRead>('/users/me', payload);
    return response.data;
  },

  createLongTermToken: async () => {
    const response = await apiClient.post<TokenResponse>('/auth/tokens');
    return response.data;
  },

  revokeLongTermToken: async () => {
    const response = await apiClient.delete<TokenRevokeResponse>('/auth/tokens');
    return response.data;
  },
};
