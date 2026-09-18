import { apiRequest } from './client'

export interface ProfilePayload {
  name?: string
  driver_age?: number
  region_id?: number
  annual_mileage_km?: number
  driver_experience_years?: number
  osago_unlimited_drivers?: boolean
  use_dealer_service?: boolean
  include_kasko?: boolean
}

export const profileApi = {
  get: (token: string | null) =>
    apiRequest<ProfilePayload>('/api/profile', { accessToken: token }),
  put: (token: string | null, payload: ProfilePayload) =>
    apiRequest<ProfilePayload>('/api/profile', {
      method: 'PUT',
      body: payload,
      accessToken: token,
    }),
  delete: (token: string | null) =>
    apiRequest<void>('/api/profile', {
      method: 'DELETE',
      accessToken: token,
    }),
}
