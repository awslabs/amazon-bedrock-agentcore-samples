import { useState, useEffect, useCallback } from 'react'
import {
  getUserSessions,
  getSessionMessages,
  type Session,
  type ChatMessage
} from '../services/bedrockSessionService'

interface UseSessionsReturn {
  sessions: Session[]
  currentSession: Session | null
  loading: boolean
  error: string | null
  switchToSession: (session: Session) => void
  startNewConversation: () => void
  refreshSessions: () => Promise<void>
  getMessages: (sessionId: string) => Promise<ChatMessage[]>
  updateCurrentSession: (session: Session) => void
}

// Helper function to generate a new session ID
const generateSessionId = (userId: string) => {
  return `session-${userId}-${Date.now()}`
}

export const useSessions = (userId: string | null): UseSessionsReturn => {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load sessions for user
  const loadSessions = useCallback(async () => {
    if (!userId) {
      setSessions([])
      setCurrentSession(null)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      
      const userSessions = await getUserSessions(userId)
      setSessions(userSessions)
      
      // Auto-select first session if no current session
      if (userSessions.length > 0 && !currentSession) {
        setCurrentSession(userSessions[0])
      } else if (userSessions.length === 0 && !currentSession) {
        // If no sessions exist, automatically start a new conversation
        console.log('No sessions found, starting new conversation')
        const newSession: Session = {
          id: generateSessionId(userId),
          userId: userId,
          title: 'New Conversation',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          isTemporary: true
        }
        setCurrentSession(newSession)
      }
    } catch (err) {
      console.error('Error loading sessions:', err)
      // Don't show error for empty sessions, just start a new conversation
      if (err instanceof Error && err.message.includes('Failed to fetch sessions')) {
        console.log('No sessions available, starting new conversation')
        const newSession: Session = {
          id: generateSessionId(userId),
          userId: userId,
          title: 'New Conversation',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          isTemporary: true
        }
        setCurrentSession(newSession)
        setError(null) // Clear any error state
      } else {
        setError('Failed to load sessions')
      }
    } finally {
      setLoading(false)
    }
  }, [userId, currentSession])

  // Switch to existing session
  const switchToSession = useCallback((session: Session) => {
    setCurrentSession(session)
  }, [])

  // Start new conversation with a new session ID
  const startNewConversation = useCallback(() => {
    if (!userId) return
    
    // Create a temporary session with a new ID
    const newSession: Session = {
      id: generateSessionId(userId),
      userId: userId,
      title: 'New Conversation',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      isTemporary: true // Mark as temporary until first message is sent
    }
    
    setCurrentSession(newSession)
  }, [userId])

  // Get messages for a session
  const getMessages = useCallback(async (sessionId: string): Promise<ChatMessage[]> => {
    if (!userId) return []
    
    try {
      return await getSessionMessages(sessionId)
    } catch (err) {
      console.error('Error getting messages:', err)
      throw err
    }
  }, [userId])

  // Update current session (used when converting temporary session to permanent)
  const updateCurrentSession = useCallback((session: Session) => {
    setCurrentSession(session)
  }, [])

  // Refresh sessions
  const refreshSessions = useCallback(async () => {
    await loadSessions()
  }, [loadSessions])

  // Load sessions on mount and when userId changes
  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  return {
    sessions,
    currentSession,
    loading,
    error,
    switchToSession,
    startNewConversation,
    refreshSessions,
    getMessages,
    updateCurrentSession
  }
}
