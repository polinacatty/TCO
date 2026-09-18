import { apiRequest } from './client'

export interface AuthPayload {
  email: string
  password: string
}

export interface RegisterPayload extends AuthPayload {
  pdn_consent: boolean
}

export interface AuthResponse {
  access_token: string
  expires_in: number
  user: {
    id: string
    email: string
    has_profile: boolean
  }
}

export const authApi = {
  login: (payload: AuthPayload) =>
    apiRequest<AuthResponse>('/api/auth/login', { method: 'POST', body: payload }),
  register: (payload: RegisterPayload) =>
    apiRequest<AuthResponse>('/api/auth/register', { method: 'POST', body: payload }),
  refresh: () => apiRequest<AuthResponse>('/api/auth/refresh', { method: 'POST' }),
  logout: () => apiRequest<void>('/api/auth/logout', { method: 'POST' }),
  me: (token: string | null) =>
    apiRequest<AuthResponse['user']>('/api/auth/me', {
      method: 'GET',
      accessToken: token,
    }),
}
