import { useState, useEffect } from 'react'
import { LogOut } from 'lucide-react'
import { Button } from './ui/button'
import { useChat } from '../hooks/useChat'
import { fetchAuthSession } from 'aws-amplify/auth'

interface SidebarProps {
  signOut: () => void
}

export function Sidebar({ signOut }: SidebarProps) {
  const { sessionId, agentArn } = useChat()
  const [accessToken, setAccessToken] = useState<string>('')

  useEffect(() => {
    const getToken = async () => {
      try {
        const session = await fetchAuthSession()
        const token = session.tokens?.accessToken?.toString() || ''
        setAccessToken(token)
      } catch (error) {
        console.error('Error fetching auth session:', error)
      }
    }
    getToken()
  }, [])

  return (
    <aside className="w-80 bg-[#1a1e27] border-r border-gray-700 flex flex-col overflow-hidden">
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold text-gray-200 mb-2">Session Info</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Access Token */}
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Access Token</h3>
          <div className="bg-[#23272f] border border-gray-600 rounded-lg p-3 text-xs text-gray-300 font-mono break-all max-h-32 overflow-y-auto">
            {accessToken ? (
              accessToken.substring(0, 100) + '...'
            ) : (
              'No token'
            )}
          </div>
        </div>

        {/* Agent ARN */}
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Agent ARN</h3>
          <div className="bg-[#23272f] border border-gray-600 rounded-lg p-3 text-xs text-gray-300 font-mono break-all">
            {agentArn || 'Not initialized'}
          </div>
        </div>

        {/* Session ID */}
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Session ID</h3>
          <div className="bg-[#23272f] border border-gray-600 rounded-lg p-3 text-xs text-gray-300 font-mono break-all">
            {sessionId}
          </div>
        </div>
      </div>

      <div className="p-4 border-t border-gray-700">
        <Button
          onClick={signOut}
          variant="destructive"
          className="w-full flex items-center justify-center gap-2"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </Button>
      </div>
    </aside>
  )
}
