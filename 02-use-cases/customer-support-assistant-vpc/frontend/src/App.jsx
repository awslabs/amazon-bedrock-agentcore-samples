import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { ChatProvider } from './hooks/useChat'
import { LoginPage } from './components/LoginPage'
import { ChatPage } from './components/ChatPage'
import { CallbackHandler } from './components/CallbackHandler'

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-[#181c24] flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    )
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function AppRoutes() {
  const { isAuthenticated, loading } = useAuth()

  // Handle OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.has('code') && params.has('state') && !isAuthenticated) {
      // Will be handled by CallbackHandler component
      return
    }
  }, [isAuthenticated])

  if (loading) {
    return (
      <div className="min-h-screen bg-[#181c24] flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route
        path="/"
        element={
          window.location.search.includes('code=') ? (
            <CallbackHandler />
          ) : (
            <ProtectedRoute>
              <ChatProvider>
                <ChatPage />
              </ChatProvider>
            </ProtectedRoute>
          )
        }
      />
    </Routes>
  )
}

function App() {
  // Get stack name from URL query parameter or use default
  const params = new URLSearchParams(window.location.search)
  const stackName = params.get('stack') || 'customer-support-vpc-dev'

  return (
    <BrowserRouter>
      <AuthProvider stackName={stackName}>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
