import { create } from 'zustand'

interface User {
  id: string
  email: string
  hasProfile: boolean
}

interface AuthState {
  isBootstrapping: boolean
  accessToken: string | null
  user: User | null
  isAuthenticated: boolean
  setBootstrapping: (value: boolean) => void
  setSession: (session: { accessToken: string; user: User }) => void
  setUserHasProfile: (value: boolean) => void
  clear: () => void
}

const STORAGE_KEY = 'tco_frontend_auth'

function loadInitialState(): Pick<AuthState, 'accessToken' | 'user' | 'isAuthenticated'> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return { accessToken: null, user: null, isAuthenticated: false }
    }
    const parsed = JSON.parse(raw) as { accessToken: string; user: User }
    if (!parsed.accessToken || !parsed.user) {
      return { accessToken: null, user: null, isAuthenticated: false }
    }
    return {
      accessToken: parsed.accessToken,
      user: parsed.user,
      isAuthenticated: true,
    }
  } catch {
    return { accessToken: null, user: null, isAuthenticated: false }
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  isBootstrapping: true,
  ...loadInitialState(),
  setBootstrapping: (value) => set({ isBootstrapping: value }),
  setSession: ({ accessToken, user }) =>
    set({
      accessToken,
      user,
      isAuthenticated: true,
    }),
  setUserHasProfile: (value) =>
    set((state) => ({
      user: state.user ? { ...state.user, hasProfile: value } : null,
    })),
  clear: () =>
    set({
      accessToken: null,
      user: null,
      isAuthenticated: false,
    }),
}))

useAuthStore.subscribe((state) => {
  if (!state.isAuthenticated || !state.accessToken || !state.user) {
    sessionStorage.removeItem(STORAGE_KEY)
    return
  }
  sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      accessToken: state.accessToken,
      user: state.user,
    }),
  )
})
