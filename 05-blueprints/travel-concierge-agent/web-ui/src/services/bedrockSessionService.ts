import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

// Create client function to ensure Amplify is configured before use
const getClient = () => generateClient<Schema>()

export interface Session {
  id: string
  userId: string
  title: string
  createdAt: string
  updatedAt: string
  lastMessage?: string
  isTemporary?: boolean // For locally created sessions not yet synced with backend
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  sessionId: string
}

/**
 * Get all sessions for a user from AppSync
 */
export const getUserSessions = async (userId: string): Promise<Session[]> => {
  try {
    const client = getClient()
    const result = await client.models.ChatSession.list({
      filter: { userId: { eq: userId } }
    })
    
    if (result.errors) {
      console.error('GraphQL errors:', result.errors)
      throw new Error('Failed to fetch sessions')
    }
    
    // Map the GraphQL response to our Session interface
    const sessions = (result.data || [])
      .filter(session => session != null)
      .map(session => ({
        id: session.id,
        userId: session.userId,
        title: session.title || session.id, // Use title or fallback to id
        createdAt: session.createdAt,
        updatedAt: session.updatedAt,
      })) as Session[]
    
    // Sort by updatedAt descending (most recent first)
    sessions.sort((a, b) => {
      const dateA = new Date(a.updatedAt || 0).getTime()
      const dateB = new Date(b.updatedAt || 0).getTime()
      return dateB - dateA
    })
    
    return sessions
  } catch (error) {
    console.error('Error fetching user sessions:', error)
    return []
  }
}

/**
 * Get messages for a specific session from AppSync
 */
export const getSessionMessages = async (sessionId: string): Promise<ChatMessage[]> => {
  try {
    const client = getClient()
    const result = await client.models.ChatMessage.list({
      filter: { sessionId: { eq: sessionId } }
    })
    
    if (result.errors) {
      console.error('GraphQL errors:', result.errors)
      throw new Error('Failed to fetch session messages')
    }
    
    // Map the GraphQL response to our ChatMessage interface
    const messages = (result.data || [])
      .filter(message => message != null)
      .map(message => ({
        id: message.id,
        role: message.role as 'user' | 'assistant',
        content: message.content,
        timestamp: message.timestamp || message.createdAt,
        sessionId: message.sessionId
      })) as ChatMessage[]
    
    // Sort by timestamp ascending (oldest first)
    messages.sort((a, b) => {
      const dateA = new Date(a.timestamp || 0).getTime()
      const dateB = new Date(b.timestamp || 0).getTime()
      return dateA - dateB
    })
    
    return messages
  } catch (error) {
    console.error('Error fetching session messages:', error)
    throw error
  }
}

/**
 * Create a new chat session
 */
export const createSession = async (userId: string, title?: string): Promise<Session> => {
  try {
    const client = getClient()
    const now = new Date().toISOString()
    
    const result = await client.models.ChatSession.create({
      userId,
      title: title || `Chat ${new Date().toLocaleString()}`,
      createdAt: now,
      updatedAt: now,
    })
    
    if (result.errors) {
      console.error('GraphQL errors:', result.errors)
      throw new Error('Failed to create session')
    }
    
    if (!result.data) {
      throw new Error('No data returned from session creation')
    }

    const sessionData = result.data as any

    return {
      id: sessionData.id,
      userId: sessionData.userId || '',
      title: sessionData.title || sessionData.id,
      createdAt: sessionData.createdAt || now,
      updatedAt: sessionData.updatedAt || now,
    }
  } catch (error) {
    console.error('Error creating session:', error)
    throw error
  }
}

/**
 * Save a message to a session
 */
export const saveMessage = async (
  sessionId: string,
  role: 'user' | 'assistant',
  content: string,
  timestamp?: string
): Promise<ChatMessage> => {
  try {
    const client = getClient()
    const now = new Date().toISOString()
    
    const result = await client.models.ChatMessage.create({
      sessionId,
      role,
      content,
      timestamp: timestamp || now,
      createdAt: now,
      updatedAt: now,
    })
    
    if (result.errors) {
      console.error('GraphQL errors:', result.errors)
      throw new Error('Failed to save message')
    }
    
    if (!result.data) {
      throw new Error('No data returned from message creation')
    }

    const messageData = result.data as any

    return {
      id: messageData.id,
      role: messageData.role as 'user' | 'assistant',
      content: messageData.content || '',
      timestamp: messageData.timestamp || messageData.createdAt || now,
      sessionId: messageData.sessionId || ''
    }
  } catch (error) {
    console.error('Error saving message:', error)
    throw error
  }
}

/**
 * Delete a session and all its messages
 */
export const deleteSession = async (sessionId: string): Promise<void> => {
  try {
    const client = getClient()
    
    // First delete all messages in the session
    const messagesResult = await client.models.ChatMessage.list({
      filter: { sessionId: { eq: sessionId } }
    })
    
    if (messagesResult.data) {
      for (const message of messagesResult.data) {
        await client.models.ChatMessage.delete({ id: message.id })
      }
    }
    
    // Then delete the session
    await client.models.ChatSession.delete({ id: sessionId })
  } catch (error) {
    console.error('Error deleting session:', error)
    throw error
  }
}

/**
 * Get the most recent session for a user
 */
export const getLastSession = async (userId: string): Promise<Session | null> => {
  const sessions = await getUserSessions(userId)
  return sessions.length > 0 ? sessions[0] : null
}
