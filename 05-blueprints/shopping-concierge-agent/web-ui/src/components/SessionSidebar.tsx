import { useState } from 'react'
import { type Session, deleteSession } from '../services/bedrockSessionService'

interface SessionSidebarProps {
  sessions: Session[]
  currentSession: Session | null
  loading: boolean
  error: string | null
  onNewConversation: () => void
  onSessionSelect: (session: Session) => void
  onSessionDelete: (sessionId: string) => void
}

const SessionSidebar = ({
  sessions,
  currentSession,
  loading,
  error,
  onNewConversation,
  onSessionSelect,
  onSessionDelete
}: SessionSidebarProps) => {
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null)
  const [isCollapsed, setIsCollapsed] = useState(false)

  const handleDeleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation() // Prevent session selection

    try {
      // Set loading state for this specific session
      setDeletingSessionId(sessionId)
      
      // Perform the actual deletion first and wait for completion
      await deleteSession(sessionId)
      onSessionDelete(sessionId)
    } catch (error) {
      console.error('Error deleting session:', error)
      // TODO: Show user-friendly error message
    } finally {
      // Clear loading state
      setDeletingSessionId(null)
    }
  }

  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInMinutes = (now.getTime() - date.getTime()) / (1000 * 60)
    const diffInHours = diffInMinutes / 60
    const diffInDays = diffInHours / 24
    
    if (diffInMinutes < 1) {
      return 'Just now'
    } else if (diffInMinutes < 60) {
      return `${Math.floor(diffInMinutes)} min ago`
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)} hour${Math.floor(diffInHours) === 1 ? '' : 's'} ago`
    } else if (diffInDays < 7) {
      return `${Math.floor(diffInDays)} day${Math.floor(diffInDays) === 1 ? '' : 's'} ago`
    } else {
      return date.toLocaleDateString()
    }
  }


  return (
    <div className={`sessions-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button 
          className="new-chat-btn"
          onClick={onNewConversation}
          disabled={loading}
          title={isCollapsed ? "New Conversation" : ""}
        >
          <svg 
            className="new-chat-icon" 
            width="20" 
            height="20" 
            viewBox="0 0 24 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              d="M12 4C11.4477 4 11 4.44772 11 5V11H5C4.44772 11 4 11.4477 4 12C4 12.5523 4.44772 13 5 13H11V19C11 19.5523 11.4477 20 12 20C12.5523 20 13 19.5523 13 19V13H19C19.5523 13 20 12.5523 20 12C20 11.4477 19.5523 11 19 11H13V5C13 4.44772 12.5523 4 12 4Z" 
              fill="currentColor"
            />
          </svg>
          {!isCollapsed && <span className="new-chat-text">New Conversation</span>}
        </button>
        <button 
          className="collapse-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg 
            width="20" 
            height="20" 
            viewBox="0 0 24 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
            style={{ transform: isCollapsed ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
          >
            <path 
              d="M15 18L9 12L15 6" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <div className="sessions-content">
        {error && (
          <div className="sessions-error">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}

        {loading && sessions.length === 0 ? (
          <div className="sessions-loading">
            <div className="loading-spinner"></div>
            <span>Loading conversations...</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="no-sessions">
            <div className="no-sessions-icon">💬</div>
            <div className="no-sessions-text">
              <p>No conversations yet</p>
              <p>Start a new conversation to begin</p>
            </div>
          </div>
        ) : (
          <div className="sessions-list">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${currentSession?.id === session.id ? 'active' : ''}`}
                onClick={() => onSessionSelect(session)}
                title={isCollapsed ? session.title : ""}
              >
                <div className="session-content">
                  <div className="session-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  {!isCollapsed && (
                    <>
                      <div className="session-topic">
                        {session.title}
                      </div>
                      <div className="session-meta">
                        <span className="session-date">
                          {formatRelativeTime(session.createdAt)}
                        </span>
                      </div>
                    </>
                  )}
                </div>
                {!isCollapsed && (
                  <button
                    className="delete-session-btn"
                    onClick={(e) => handleDeleteSession(session.id, e)}
                    disabled={deletingSessionId === session.id}
                    title={deletingSessionId === session.id ? "Deleting..." : "Delete conversation"}
                  >
                    {deletingSessionId === session.id ? (
                      <div className="loading-spinner-small"></div>
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                        <path 
                          d="M18 6L6 18M6 6l12 12" 
                          stroke="currentColor" 
                          strokeWidth="2" 
                          strokeLinecap="round" 
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SessionSidebar
