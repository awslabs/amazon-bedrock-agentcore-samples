import { useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { Loader2 } from 'lucide-react'

export function LoginPage() {
  const { login, loading } = useAuth()

  useEffect(() => {
    if (!loading) {
      login()
    }
  }, [loading, login])

  return (
    <div className="min-h-screen bg-[#181c24] flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
        <h1 className="text-2xl font-semibold text-gray-200 mb-2">
          Customer Support Assistant
        </h1>
        <p className="text-gray-400">Redirecting to login...</p>
      </div>
    </div>
  )
}
