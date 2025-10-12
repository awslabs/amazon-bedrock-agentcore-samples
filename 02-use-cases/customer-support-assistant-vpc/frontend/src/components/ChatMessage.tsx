import { memo } from 'react'
import { Bot, User } from 'lucide-react'
import { cn, makeUrlsClickable, formatElapsedTime } from '../lib/utils'
import type { Message } from '../types'

interface ChatMessageProps {
  message: Message
  isStreaming?: boolean
}

export const ChatMessage = memo(function ChatMessage({
  message,
  isStreaming = false,
}: ChatMessageProps) {
  const isUser = message.role === 'user'
  const contentWithLinks = makeUrlsClickable(message.content)

  return (
    <div
      className={cn(
        "flex w-full animate-fade-in-up",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "flex gap-3 max-w-[85%] rounded-2xl px-4 py-3 shadow-sm",
          isUser
            ? "bg-[#23272f] text-gray-200 border border-[#3a3f4b]"
            : cn(
                "bg-[#0b2545] text-gray-200 border",
                isStreaming
                  ? "border-[#4fc3f7] shadow-[0_0_10px_rgba(79,195,247,0.3)] animate-pulse-border"
                  : "border-[#298dff]"
              )
        )}
      >
        <div className="flex-shrink-0 mt-1">
          {isUser ? (
            <User className="w-5 h-5 text-gray-400" />
          ) : (
            <Bot className="w-5 h-5 text-blue-400" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div
            className={cn(
              "whitespace-pre-wrap break-words text-sm leading-relaxed",
              isStreaming && "relative"
            )}
            dangerouslySetInnerHTML={{ __html: contentWithLinks }}
          />

          {isStreaming && (
            <span className="inline-block ml-1 text-[#4fc3f7] animate-cursor-blink">▋</span>
          )}

          {!isUser && message.elapsed !== undefined && !isStreaming && (
            <div className="mt-2 text-xs text-gray-500">
              ⏱️ Response time: {formatElapsedTime(message.elapsed)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
})
