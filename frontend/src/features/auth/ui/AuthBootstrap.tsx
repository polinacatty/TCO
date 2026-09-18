import type { PropsWithChildren } from 'react'
import { useEffect } from 'react'

import { authApi } from '../../../shared/api/auth'
import type { ApiError } from '../../../shared/api/types'
import { useAuthStore } from '../model/useAuthStore'

export function AuthBootstrap({ children }: PropsWithChildren) {
  const accessToken = useAuthStore((state) => state.accessToken)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const setSession = useAuthStore((state) => state.setSession)
  const clear = useAuthStore((state) => state.clear)
  const setBootstrapping = useAuthStore((state) => state.setBootstrapping)

  useEffect(() => {
    let active = true
    const run = async () => {
      try {
        if (isAuthenticated && accessToken) {
          const me = await authApi.me(accessToken)
          if (!active) return
          setSession({
            accessToken,
            user: {
              id: me.id,
              email: me.email,
              hasProfile: me.has_profile,
            },
          })
          return
        }
        const refreshed = await authApi.refresh()
        if (!active) return
        setSession({
          accessToken: refreshed.access_token,
          user: {
            id: refreshed.user.id,
            email: refreshed.user.email,
            hasProfile: refreshed.user.has_profile,
          },
        })
      } catch (error) {
        if (!active) return
        const apiError = error as ApiError
        if (apiError.status === 401) {
          clear()
        }
      } finally {
        if (active) {
          setBootstrapping(false)
        }
      }
    }
    void run()
    return () => {
      active = false
    }
  }, [accessToken, clear, isAuthenticated, setBootstrapping, setSession])

  return <>{children}</>
}
