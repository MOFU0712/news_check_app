import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Articles from './pages/Articles'
import ArticleDetail from './pages/ArticleDetail'
import Reports from './pages/Reports'
import UserManagement from './pages/UserManagement'
import Settings from './pages/Settings'
import { ScrapingPage } from './pages/ScrapingPage'
import { TestScrapingComponents } from './components/scraping/TestScrapingComponents'
import LoadingSpinner from './components/LoadingSpinner'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <LoadingSpinner />
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <LoadingSpinner />
  }

  return isAuthenticated ? <Navigate to="/" replace /> : <>{children}</>
}

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={
        <PublicRoute>
          <Login />
        </PublicRoute>
      } />

      {/* Protected routes */}
      <Route path="/" element={
        <ProtectedRoute>
          <Layout>
            <Dashboard />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/articles" element={
        <ProtectedRoute>
          <Layout>
            <Articles />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/articles/:id" element={
        <ProtectedRoute>
          <Layout>
            <ArticleDetail />
          </Layout>
        </ProtectedRoute>
      } />

      {/* Placeholder routes */}
      <Route path="/search" element={
        <ProtectedRoute>
          <Layout>
            <div className="text-center py-12">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">検索機能</h2>
              <p className="text-gray-600">Phase 2で実装予定</p>
            </div>
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/scrape" element={
        <ProtectedRoute>
          <Layout>
            <ScrapingPage />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/test-scraping" element={
        <ProtectedRoute>
          <Layout>
            <TestScrapingComponents />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/reports" element={
        <ProtectedRoute>
          <Layout>
            <Reports />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/admin/users" element={
        <ProtectedRoute>
          <Layout>
            <UserManagement />
          </Layout>
        </ProtectedRoute>
      } />

      <Route path="/admin/settings" element={
        <ProtectedRoute>
          <Layout>
            <Settings />
          </Layout>
        </ProtectedRoute>
      } />

      {/* Catch all route */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App