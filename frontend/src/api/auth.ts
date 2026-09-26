import { apiRequest } from './fetch';
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
  login: (body: AuthLoginRequest) =>
    apiRequest<LoginResponse>('POST', '/auth/login', { body }),
  register: (body: AuthRegisterRequest) =>
    apiRequest<MessageResponse>('POST', '/auth/register', { body }),
  googleLogin: (body: GoogleLoginRequest) =>
    apiRequest<LoginResponse>('POST', '/auth/google', { body }),
  getMe: () => apiRequest<UserProfileRead>('GET', '/users/me'),
  updateProfile: (body: UserProfileUpdate) =>
    apiRequest<UserProfileRead>('PATCH', '/users/me', { body }),
  createLongTermToken: () => apiRequest<TokenResponse>('POST', '/auth/tokens'),
  revokeLongTermToken: () =>
    apiRequest<TokenRevokeResponse>('DELETE', '/auth/tokens'),
};
