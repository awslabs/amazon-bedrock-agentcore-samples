import { useEffect, useRef } from 'react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { ScrollArea } from './ui/scroll-area'
import { useChat } from '../hooks/useChat'
import { useAuth } from '../hooks/useAuth'
import { Loader2 } from 'lucide-react'

export function ChatContainer() {
  const { messages, sendMessage, isStreaming, isInitialized, initializationError, initializeConversation } = useChat()
  const { tokens, userClaims } = useAuth()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const hasInitialized = useRef(false)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Initialize conversation on first load
  useEffect(() => {
    if (
      isInitialized &&
      !hasInitialized.current &&
      messages.length === 0 &&
      tokens &&
      userClaims
    ) {
      hasInitialized.current = true
      initializeConversation(
        userClaims.email,
        tokens.access_token,
        userClaims['cognito:username']
      )
    }
  }, [isInitialized, messages.length, tokens, userClaims, initializeConversation])

  const handleSendMessage = async (message: string) => {
    if (!tokens || !userClaims) return

    await sendMessage(
      message,
      tokens.access_token,
      userClaims['cognito:username']
    )
  }

  if (initializationError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-2">❌ {initializationError}</p>
          <p className="text-gray-400 text-sm">Please check your CloudFormation stack configuration</p>
        </div>
      </div>
    )
  }

  if (!isInitialized) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-gray-400">Initializing agent...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <ScrollArea className="flex-1 px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((message, index) => {
            const isLastMessage = index === messages.length - 1
            const isStreamingMessage = isStreaming && isLastMessage && message.role === 'assistant'

            return (
              <ChatMessage
                key={`${message.timestamp}-${index}`}
                message={message}
                isStreaming={isStreamingMessage}
              />
            )
          })}

          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <div className="flex justify-start">
              <div className="bg-[#0b2545] text-gray-200 border border-[#298dff] rounded-2xl px-4 py-3 animate-thinking-pulse">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">💭 Customer Support Assistant is thinking...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      <ChatInput
        onSend={handleSendMessage}
        disabled={isStreaming}
      />
    </div>
  )
}
