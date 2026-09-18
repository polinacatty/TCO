import { env } from '../config/env'
import { useAuthStore } from '../../features/auth/model/useAuthStore'
import type { ApiError, ProblemDetails } from './types'

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  accessToken?: string | null
}

export async function apiRequest<T>(
  path: string,
  { body, accessToken, headers, ...rest }: RequestOptions = {},
): Promise<T> {
  const doFetch = (tokenOverride?: string | null) =>
    fetch(`${env.apiBaseUrl}${path}`, {
      credentials: 'include',
      ...rest,
      headers: {
        'Content-Type': 'application/json',
        ...(tokenOverride ? { Authorization: `Bearer ${tokenOverride}` } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })

  const isAuthEndpoint = path.startsWith('/api/auth/')
  let response = await doFetch(accessToken)

  if (response.status === 401 && !isAuthEndpoint) {
    try {
      const refreshResponse = await fetch(`${env.apiBaseUrl}/api/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      if (refreshResponse.ok) {
        const refreshed = (await refreshResponse.json()) as {
          access_token: string
          user: { id: string; email: string; has_profile: boolean }
        }
        useAuthStore.getState().setSession({
          accessToken: refreshed.access_token,
          user: {
            id: refreshed.user.id,
            email: refreshed.user.email,
            hasProfile: refreshed.user.has_profile,
          },
        })
        response = await doFetch(refreshed.access_token)
      } else {
        useAuthStore.getState().clear()
      }
    } catch {
      useAuthStore.getState().clear()
    }
  }

  if (!response.ok) {
    let details: ProblemDetails | null = null
    try {
      details = (await response.json()) as ProblemDetails
    } catch {
      details = null
    }
    const error = new Error(details?.detail || 'Request failed') as ApiError
    error.status = response.status
    error.details = details
    throw error
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
