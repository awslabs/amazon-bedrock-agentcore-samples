import { useEffect, useRef, useState } from 'react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { useChat } from '../hooks/useChat';
import { getBearerToken } from '../services/authService';
import { Loader2 } from 'lucide-react';

export function ChatContainer() {
  const { messages, sendMessage, isStreaming, isInitialized, initializationError, initializeConversation } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasInitialized = useRef(false);
  const [bearerToken, setBearerToken] = useState<string>('');
  const [authError, setAuthError] = useState<string | null>(null);

  // Fetch bearer token on mount
  useEffect(() => {
    const fetchToken = async () => {
      try {
        const token = await getBearerToken();
        setBearerToken(token);
      } catch (error) {
        console.error('Failed to get bearer token:', error);
        setAuthError(error instanceof Error ? error.message : 'Failed to authenticate');
      }
    };
    fetchToken();
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize conversation on first load
  useEffect(() => {
    if (
      isInitialized &&
      !hasInitialized.current &&
      messages.length === 0 &&
      bearerToken
    ) {
      hasInitialized.current = true;
      initializeConversation(
        bearerToken,
        'guest'
      );
    }
  }, [isInitialized, messages.length, bearerToken, initializeConversation]);

  const handleSendMessage = async (message: string) => {
    if (!bearerToken) {
      console.error('No bearer token available');
      return;
    }
    await sendMessage(
      message,
      bearerToken,
      'guest'
    );
  };

  if (authError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-2">❌ Authentication Error</p>
          <p className="text-gray-400 text-sm">{authError}</p>
          <p className="text-gray-400 text-sm mt-2">Please check your Cognito configuration in .env file</p>
        </div>
      </div>
    );
  }

  if (initializationError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-2">❌ {initializationError}</p>
          <p className="text-gray-400 text-sm">Please check your CloudFormation stack configuration</p>
        </div>
      </div>
    );
  }

  if (!isInitialized) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-gray-400">Initializing agent...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full">
      {/* Scrollable message history */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((message, index) => {
            const isLastMessage = index === messages.length - 1;
            const isStreamingMessage = isStreaming && isLastMessage && message.role === 'assistant';

            return (
              <ChatMessage
                key={`${message.timestamp}-${index}`}
                message={message}
                isStreaming={isStreamingMessage}
              />
            );
          })}

          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <div className="flex justify-start">
              <div className="bg-[#0b2545] text-gray-200 border border-[#298dff] rounded-2xl px-4 py-3 animate-thinking-pulse">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">💭 Host Agent is thinking...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Fixed chat input at bottom */}
      <div className="flex-shrink-0">
        <ChatInput
          onSend={handleSendMessage}
          disabled={isStreaming}
        />
      </div>
    </div>
  );
}
