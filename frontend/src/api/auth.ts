import apiClient from './client';
import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  GoogleLoginRequest,
  LoginResponse,
  MessageResponse,
  TokenResponse,
  TokenRevokeResponse,
  UserProfileRead,
  UserProfileUpdate,
} from './types';

export const authApi = {
  login: async (payload: AuthLoginRequest) => {
    const response = await apiClient.post<LoginResponse>('/auth/login', payload);
    return response.data;
  },

  register: async (payload: AuthRegisterRequest) => {
    const response = await apiClient.post<MessageResponse>('/auth/register', payload);
    return response.data;
  },

  googleLogin: async (payload: GoogleLoginRequest) => {
    const response = await apiClient.post<LoginResponse>('/auth/google', payload);
    return response.data;
  },

  getMe: async () => {
    const response = await apiClient.get<UserProfileRead>('/users/me');
    return response.data;
  },

  updateProfile: async (payload: UserProfileUpdate) => {
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
