import { apiRequest } from './fetch';
import type {
  ApiTokenCreated,
  ApiTokenRead,
  AuthLoginRequest,
  AuthRegisterRequest,
  GoogleLoginRequest,
  LoginResponse,
  MessageResponse,
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
  listTokens: () => apiRequest<ApiTokenRead[]>('GET', '/auth/tokens'),
  createToken: (name: string) =>
    apiRequest<ApiTokenCreated>('POST', '/auth/tokens', { body: { name } }),
  revokeToken: (tokenId: number) =>
    apiRequest<MessageResponse>('DELETE', `/auth/tokens/${tokenId}`),
};
