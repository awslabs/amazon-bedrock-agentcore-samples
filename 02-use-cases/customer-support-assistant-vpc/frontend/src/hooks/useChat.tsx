import { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react'
import type { ChatState, Message } from '../types'
import { getAgentARNFromStack } from '../services/awsService'
import { invokeAgentStream } from '../services/chatService'
import { generateUUID } from '../lib/utils'

interface ChatContextType extends ChatState {
  sendMessage: (message: string, bearerToken: string, actorId: string) => Promise<void>
  initializeConversation: (email: string, bearerToken: string, actorId: string) => Promise<void>
  clearMessages: () => void
  isInitialized: boolean
  initializationError: string | null
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)

interface ChatProviderProps {
  children: ReactNode
  stackName?: string
}

export function ChatProvider({ children, stackName = 'customer-support-vpc' }: ChatProviderProps) {
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    isStreaming: false,
    sessionId: generateUUID(),
    agentArn: '',
    region: '',
  })

  const [isInitialized, setIsInitialized] = useState(false)
  const [initializationError, setInitializationError] = useState<string | null>(null)

  // Initialize agent ARN from CloudFormation
  useEffect(() => {
    const initializeAgent = async () => {
      try {
        const { agentArn, region } = await getAgentARNFromStack(stackName)
        setChatState((prev) => ({
          ...prev,
          agentArn,
          region,
        }))
        setIsInitialized(true)
      } catch (error) {
        console.error('Error initializing agent:', error)
        setInitializationError('Failed to initialize agent configuration')
      }
    }

    initializeAgent()
  }, [stackName])

  const sendMessage = useCallback(
    async (message: string, bearerToken: string, actorId: string) => {
      if (!chatState.agentArn || !chatState.region) {
        throw new Error('Agent not initialized')
      }

      // Add user message
      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: Date.now(),
      }

      setChatState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isStreaming: true,
      }))

      const startTime = Date.now()
      let accumulatedResponse = ''

      try {
        for await (const chunk of invokeAgentStream(
          chatState.agentArn,
          chatState.region,
          chatState.sessionId,
          bearerToken,
          message,
          actorId
        )) {
          if (chunk.trim()) {
            accumulatedResponse += chunk

            // Update streaming message
            setChatState((prev) => {
              const messages = [...prev.messages]
              const lastMessage = messages[messages.length - 1]

              if (lastMessage && lastMessage.role === 'assistant') {
                // Update existing assistant message
                messages[messages.length - 1] = {
                  ...lastMessage,
                  content: accumulatedResponse,
                }
              } else {
                // Add new assistant message
                messages.push({
                  role: 'assistant',
                  content: accumulatedResponse,
                  timestamp: Date.now(),
                })
              }

              return {
                ...prev,
                messages,
              }
            })
          }
        }

        const elapsed = (Date.now() - startTime) / 1000

        // Finalize message with elapsed time
        setChatState((prev) => {
          const messages = [...prev.messages]
          const lastMessage = messages[messages.length - 1]

          if (lastMessage && lastMessage.role === 'assistant') {
            messages[messages.length - 1] = {
              ...lastMessage,
              elapsed,
            }
          }

          return {
            ...prev,
            messages,
            isStreaming: false,
          }
        })
      } catch (error) {
        console.error('Error sending message:', error)
        setChatState((prev) => ({
          ...prev,
          isStreaming: false,
        }))

        // Add error message
        setChatState((prev) => ({
          ...prev,
          messages: [
            ...prev.messages,
            {
              role: 'assistant',
              content: `Error: Failed to get response from assistant. ${error instanceof Error ? error.message : 'Unknown error'}`,
              timestamp: Date.now(),
            },
          ],
        }))
      }
    },
    [chatState.agentArn, chatState.region, chatState.sessionId]
  )

  const initializeConversation = useCallback(
    async (email: string, bearerToken: string, actorId: string) => {
      const defaultPrompt = `Hi my email is ${email}`
      await sendMessage(defaultPrompt, bearerToken, actorId)
    },
    [sendMessage]
  )

  const clearMessages = useCallback(() => {
    setChatState((prev) => ({
      ...prev,
      messages: [],
      sessionId: generateUUID(),
    }))
  }, [])

  return (
    <ChatContext.Provider
      value={{
        ...chatState,
        sendMessage,
        initializeConversation,
        clearMessages,
        isInitialized,
        initializationError,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const context = useContext(ChatContext)
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}
