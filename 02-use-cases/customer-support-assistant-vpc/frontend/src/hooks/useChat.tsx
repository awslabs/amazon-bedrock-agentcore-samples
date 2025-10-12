import { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react';
import type { ChatState, Message, ToolUseBlock, MessageMetadata, StreamingEvent } from '../types';
import { invokeAgentStream } from '../services/chatService';
import { generateUUID } from '../utils';

interface ChatContextType extends ChatState {
  sendMessage: (message: string, bearerToken: string, actorId: string) => Promise<void>;
  initializeConversation: (email: string, bearerToken: string, actorId: string) => Promise<void>;
  clearMessages: () => void;
  isInitialized: boolean;
  initializationError: string | null;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

interface ChatProviderProps {
  children: ReactNode;
}

export function ChatProvider({ children }: ChatProviderProps) {
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    isStreaming: false,
    sessionId: generateUUID(),
    agentArn: import.meta.env.VITE_AGENT_ARN || '',
    region: import.meta.env.VITE_AWS_REGION || 'us-west-2',
  });

  const [isInitialized, setIsInitialized] = useState(false);
  const [initializationError, setInitializationError] = useState<string | null>(null);

  // Initialize agent from environment variables
  useEffect(() => {
    const agentArn = import.meta.env.VITE_AGENT_ARN;
    const region = import.meta.env.VITE_AWS_REGION;

    if (!agentArn) {
      setInitializationError('Agent ARN not configured. Please set VITE_AGENT_ARN in .env file');
      return;
    }

    setIsInitialized(true);
  }, []);

  const sendMessage = useCallback(
    async (message: string, bearerToken: string, actorId: string) => {
      if (!chatState.agentArn || !chatState.region) {
        throw new Error('Agent not initialized');
      }

      // Add user message
      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: Date.now(),
      };

      setChatState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isStreaming: true,
      }));

      const startTime = Date.now();
      let accumulatedResponse = '';
      const toolBlocks: Map<string, ToolUseBlock> = new Map();
      let metadata: MessageMetadata = {};

      try {
        for await (const event of invokeAgentStream(
          chatState.agentArn,
          chatState.region,
          chatState.sessionId,
          bearerToken,
          message,
          actorId
        )) {
          console.log('[useChat] Received event:', event, 'Type:', typeof event, 'Is object:', typeof event === 'object' && event !== null)

          // Type guard: ensure event is an object
          if (typeof event !== 'object' || event === null) {
            console.warn('[useChat] Event is not an object, skipping:', typeof event)
            continue
          }

          // Handle nested event structure: {event: {contentBlockDelta: {delta: {text: "..."}}}}
          if ('event' in event && event.event && typeof event.event === 'object') {
            const innerEvent = event.event as any;

            // Handle contentBlockDelta events
            if ('contentBlockDelta' in innerEvent) {
              const delta = innerEvent.contentBlockDelta?.delta;
              if (delta?.text) {
                console.log('[useChat] Adding text:', delta.text)
                accumulatedResponse += delta.text;
              }
            }

            // Handle messageStop events
            if ('messageStop' in innerEvent) {
              metadata.stopReason = innerEvent.messageStop?.stopReason;
            }

            // Handle metadata events
            if ('metadata' in innerEvent) {
              const meta = innerEvent.metadata;
              if (meta?.usage) {
                metadata.usage = meta.usage;
              }
              if (meta?.metrics) {
                metadata.metrics = meta.metrics;
              }
            }
          }

          // Handle direct text delta events (fallback format: {data: "...", delta: {text: "..."}})
          else if ('delta' in event && event.delta && typeof event.delta === 'object' && 'text' in event.delta) {
            const text = (event.delta as any).text;
            if (text) {
              console.log('[useChat] Adding text (direct):', text)
              accumulatedResponse += text;
            }
          }
          // Handle simple data events
          else if ('data' in event && typeof event.data === 'string') {
            console.log('[useChat] Adding data:', event.data)
            accumulatedResponse += event.data;
          }

          // Handle current_tool_use events
          if ('current_tool_use' in event) {
            const toolUse = event.current_tool_use as any;
            const { toolUseId, name, input } = toolUse;
            toolBlocks.set(toolUseId, {
              toolUseId,
              name,
              input: input || {},
              status: 'loading',
            });
          }

          // Handle tool stream events (results)
          if ('tool_stream_event' in event) {
            const toolStreamEvent = event.tool_stream_event as any;
            const { tool_use, data } = toolStreamEvent;
            const existing = toolBlocks.get(tool_use.toolUseId);
            if (existing) {
              toolBlocks.set(tool_use.toolUseId, {
                ...existing,
                result: (existing.result || '') + data,
                status: 'success',
              });
            }
          }

          // Handle final result event
          if ('result' in event) {
            const result = event.result as any;
            if (result.tool_metrics) {
              metadata.toolMetrics = result.tool_metrics;
            }
            if (result.cycle_durations) {
              metadata.cycleDurations = result.cycle_durations;
            }
            if (result.accumulated_usage) {
              metadata.usage = {
                inputTokens: result.accumulated_usage.input_tokens,
                outputTokens: result.accumulated_usage.output_tokens,
                totalTokens: result.accumulated_usage.input_tokens + result.accumulated_usage.output_tokens,
              };
            }
          }

          // Handle metadata in event
          if ('metadata' in event) {
            const meta = event.metadata as any;
            if (meta?.usage) {
              metadata.usage = meta.usage;
            }
            if (meta?.metrics) {
              metadata.metrics = meta.metrics;
            }
          }

          // Handle stop_reason
          if ('stop_reason' in event) {
            metadata.stopReason = event.stop_reason as string;
          }

          // Update streaming message
          setChatState((prev) => {
            const messages = [...prev.messages];
            const lastMessage = messages[messages.length - 1];

            if (lastMessage && lastMessage.role === 'assistant') {
              // Update existing assistant message
              messages[messages.length - 1] = {
                ...lastMessage,
                content: accumulatedResponse,
                toolBlocks: Array.from(toolBlocks.values()),
                metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
              };
            } else {
              // Add new assistant message
              messages.push({
                role: 'assistant',
                content: accumulatedResponse,
                timestamp: Date.now(),
                toolBlocks: Array.from(toolBlocks.values()),
                metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
              });
            }

            return {
              ...prev,
              messages,
            };
          });
        }

        const elapsed = (Date.now() - startTime) / 1000;
        const totalLatencyMs = Date.now() - startTime;

        // Finalize message with elapsed time and total latency
        setChatState((prev) => {
          const messages = [...prev.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage && lastMessage.role === 'assistant') {
            // Add total latency to metadata
            const finalMetadata = {
              ...lastMessage.metadata,
              metrics: {
                ...lastMessage.metadata?.metrics,
                latencyMs: lastMessage.metadata?.metrics?.latencyMs || 0,
                totalLatencyMs,
              },
            };

            messages[messages.length - 1] = {
              ...lastMessage,
              elapsed,
              metadata: Object.keys(finalMetadata).length > 0 ? finalMetadata : undefined,
            };
          }

          return {
            ...prev,
            messages,
            isStreaming: false,
          };
        });
      } catch (error) {
        console.error('Error sending message:', error);
        setChatState((prev) => ({
          ...prev,
          isStreaming: false,
        }));

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
        }));
      }
    },
    [chatState.agentArn, chatState.region, chatState.sessionId]
  );

  const initializeConversation = useCallback(
    async (email: string, bearerToken: string, actorId: string) => {
      const defaultPrompt = `Hi, how are you doing?`;
      await sendMessage(defaultPrompt, bearerToken, actorId);
    },
    [sendMessage]
  );

  const clearMessages = useCallback(() => {
    setChatState((prev) => ({
      ...prev,
      messages: [],
      sessionId: generateUUID(),
    }));
  }, []);

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
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
