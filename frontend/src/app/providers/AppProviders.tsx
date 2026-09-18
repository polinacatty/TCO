import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { PropsWithChildren } from 'react'
import { BrowserRouter } from 'react-router-dom'

import { AuthBootstrap } from '../../features/auth/ui/AuthBootstrap'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthBootstrap>{children}</AuthBootstrap>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
