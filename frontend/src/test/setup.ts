import '@testing-library/jest-dom/vitest'

import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

import { useAuthStore } from '../features/auth/model/useAuthStore'
import { useCompareStore } from '../features/compare/model/useCompareStore'

beforeEach(() => {
  sessionStorage.clear()
  useAuthStore.setState({
    accessToken: null,
    user: null,
    isAuthenticated: false,
    isBootstrapping: false,
  })
  useCompareStore.setState({ modificationIds: [] })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})
