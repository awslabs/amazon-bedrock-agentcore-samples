import { useEffect } from 'react'
import Chat from './Chat'
import { Session, ChatMessage } from '../services/bedrockSessionService'

// Test component to verify message display
const ChatTest = () => {
  const mockUser = {
    username: 'TestUser',
    userId: 'test-user-123'
  }

  const mockSession: Session = {
    id: 'test-session-123',
    userId: 'test-user-123',
    title: 'Test Conversation',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    lastMessage: 'This is a test'
  }

  // Mock messages with the format you're receiving
  const mockGetMessages = async (sessionId: string): Promise<ChatMessage[]> => {
    console.log('Mock getMessages called with sessionId:', sessionId)
    
    // Simulate the format you're receiving from the backend
    const rawMessages = [
      {
        conversational: {
          content: { text: "Hello! How can I assist you today?" },
          role: "ASSISTANT"
        }
      },
      {
        conversational: {
          content: { text: "Hi" },
          role: "USER"
        }
      }
    ]

    // This simulates what should happen in the backend
    const parsedMessages: ChatMessage[] = rawMessages.map((msg, index) => {
      const messageData = msg.conversational
      const role = messageData.role.toLowerCase() as 'user' | 'assistant'
      const content = messageData.content.text

      return {
        id: `msg-${index}`,
        role: role,
        content: content,
        timestamp: new Date().toISOString(),
        sessionId: sessionId
      }
    })

    console.log('Returning parsed messages:', parsedMessages)
    return parsedMessages
  }

  useEffect(() => {
    // Log to show what the component is doing
    console.log('ChatTest component mounted')
  }, [])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '1rem', background: '#f0f0f0' }}>
        <h2>Chat Test Component</h2>
        <p>This component tests the message display with mock data</p>
      </div>
      <div style={{ flex: 1 }}>
        <Chat 
          user={mockUser}
          onSignOut={() => console.log('Sign out clicked')}
          currentSession={mockSession}
          getMessages={mockGetMessages}
        />
      </div>
    </div>
  )
}

export default ChatTest
