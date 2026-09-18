import { Navigate, Route, Routes } from 'react-router-dom'

import { CalculatePage } from '../../pages/CalculatePage'
import { ComparePage } from '../../pages/ComparePage'
import { DashboardPage } from '../../pages/DashboardPage'
import { FavoritesPage } from '../../pages/FavoritesPage'
import { LoginPage } from '../../pages/LoginPage'
import { NotFoundPage } from '../../pages/NotFoundPage'
import { ProfilePage } from '../../pages/ProfilePage'
import { RecommendPage } from '../../pages/RecommendPage'
import { RegisterPage } from '../../pages/RegisterPage'
import { SavedComparisonsPage } from '../../pages/SavedComparisonsPage'
import { AppLayout } from '../layout/AppLayout'
import { GuestOnlyRoute, ProtectedRoute } from './guards'

export function AppRouter() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate replace to="/dashboard" />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/calculate" element={<CalculatePage />} />
        <Route path="/recommend" element={<RecommendPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route
          path="/saved-comparisons"
          element={
            <ProtectedRoute>
              <SavedComparisonsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/favorites"
          element={
            <ProtectedRoute>
              <FavoritesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/login"
          element={
            <GuestOnlyRoute>
              <LoginPage />
            </GuestOnlyRoute>
          }
        />
        <Route
          path="/register"
          element={
            <GuestOnlyRoute>
              <RegisterPage />
            </GuestOnlyRoute>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppLayout>
  )
}
