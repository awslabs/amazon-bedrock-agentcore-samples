import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Loader2, AlertCircle } from 'lucide-react'

export function CallbackHandler() {
  const { handleCallback } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const processCallback = async () => {
      const params = new URLSearchParams(window.location.search)
      const code = params.get('code')
      const state = params.get('state')

      if (!code || !state) {
        setError('Missing authorization code or state')
        return
      }

      try {
        await handleCallback(code, state)
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname)
        // Navigate to chat
        navigate('/', { replace: true })
      } catch (error) {
        console.error('Callback error:', error)
        setError(error instanceof Error ? error.message : 'Authentication failed')
      }
    }

    processCallback()
  }, [handleCallback, navigate])

  if (error) {
    return (
      <div className="min-h-screen bg-[#181c24] flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-semibold text-gray-200 mb-2">
            Authentication Error
          </h1>
          <p className="text-gray-400 mb-4">{error}</p>
          <button
            onClick={() => navigate('/', { replace: true })}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#181c24] flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
        <h1 className="text-2xl font-semibold text-gray-200 mb-2">
          Completing authentication...
        </h1>
        <p className="text-gray-400">Please wait</p>
      </div>
    </div>
  )
}
