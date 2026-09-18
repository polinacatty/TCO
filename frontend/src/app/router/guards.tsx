import type { PropsWithChildren } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuthStore } from '../../features/auth/model/useAuthStore'

export function ProtectedRoute({ children }: PropsWithChildren) {
  const isBootstrapping = useAuthStore((state) => state.isBootstrapping)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (isBootstrapping) {
    return <div className="py-16 text-center text-sm text-slate-500">Проверяем сессию...</div>
  }
  if (!isAuthenticated) {
    return <Navigate replace to="/login" />
  }
  return children
}

export function GuestOnlyRoute({ children }: PropsWithChildren) {
  const isBootstrapping = useAuthStore((state) => state.isBootstrapping)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (isBootstrapping) {
    return <div className="py-16 text-center text-sm text-slate-500">Проверяем сессию...</div>
  }
  if (isAuthenticated) {
    return <Navigate replace to="/dashboard" />
  }
  return children
}
