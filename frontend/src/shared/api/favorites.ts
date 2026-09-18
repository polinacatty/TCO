import { apiRequest } from './client'

export interface FavoriteItem {
  modification_id: number
  created_at: string
}

export interface FavoriteListResponse {
  items: FavoriteItem[]
}

export const favoritesApi = {
  list: (token: string | null) =>
    apiRequest<FavoriteListResponse>('/api/favorites', { accessToken: token }),
  add: (token: string | null, modificationId: number) =>
    apiRequest<FavoriteListResponse>('/api/favorites', {
      method: 'POST',
      body: { modification_id: modificationId },
      accessToken: token,
    }),
  remove: (token: string | null, modificationId: number) =>
    apiRequest<FavoriteListResponse>(`/api/favorites/${modificationId}`, {
      method: 'DELETE',
      accessToken: token,
    }),
}
