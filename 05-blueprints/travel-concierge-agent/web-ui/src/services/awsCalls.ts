import { fetchAuthSession } from 'aws-amplify/auth';

// Simple UUID generator to avoid external dependency
const generateId = () => Math.random().toString(36).substring(2) + Date.now().toString(36);

// Configuration from environment variables
const AGENT_CONFIG = {
  AGENT_RUNTIME_ARN: import.meta.env.VITE_AGENT_RUNTIME_ARN || '',
  AGENT_ENDPOINT_NAME: import.meta.env.VITE_AGENT_ENDPOINT_NAME || 'DEFAULT',
  AWS_REGION: import.meta.env.VITE_AWS_REGION || 'us-east-1',
  LOCAL_ENDPOINT: import.meta.env.VITE_LOCAL_ENDPOINT || '',
};

// Bedrock Agent Core endpoint - use localhost if configured, otherwise AWS
const BEDROCK_AGENT_CORE_ENDPOINT_URL = AGENT_CONFIG.LOCAL_ENDPOINT || 
  `https://bedrock-agentcore.${AGENT_CONFIG.AWS_REGION}.amazonaws.com`;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinkingContent?: string;
  isStreaming?: boolean;
  status?: string;
  // Fields for loop management
  previousLoops?: string[];  // Array of previous loop contents
  currentLoop?: string;      // Current active loop content
  // Fields for subagent tracking
  subagentSteps?: SubagentStep[];  // Track subagent activities
  currentSubagent?: {
    name: string;
    input: string;
    tool?: string;
    content?: string;  // Current streaming content
  };
  // Purchase confirmation
  purchaseConfirmation?: {
    requires_confirmation: boolean;
    cart_items: unknown[];
    total_amount: string;
    items_count: number;
    payment_method: string;
    message: string;
  };
  // UI actions for agent-driven buttons and interactions
  ui_actions?: Array<{
    type: 'show_button';
    action: 'ADD_CARD' | 'CONFIRM_PURCHASE';
    label?: string;
    metadata?: Record<string, unknown>;
  }>;
  // Card check result from check_user_has_payment_card tool
  card_check_result?: {
    has_card: boolean;
    has_primary: boolean;
    has_backup: boolean;
    card_info?: {
      type: string;
      last_four: string;
      is_primary: boolean;
    } | null;
  };
}

export interface SubagentStep {
  agentName: string;
  input: string;
  content: string;
  tools?: string[];
  timestamp: number;
}

// Helper to check if a line should be skipped (noise from backend)
const shouldSkipLine = (line: string): boolean => {
  // Skip Python repr strings (raw Strands events with non-serializable objects)
  if (line.startsWith("\"{'") || line.startsWith("{'")) return true;
  
  // Skip control events
  if (line.includes('"init_event_loop"') || 
      line.includes('"start": true') ||
      line.includes('"start_event_loop"')) return true;
  
  return false;
};

/**
 * Invokes the agent core functionality with streaming support
 */
export const invokeAgentCore = async (
  query: string,
  userId: string,
  sessionId: string,
  setAnswers: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void,
): Promise<{
  sessionId: string;
  completion: string;
}> => {
  try {
    // Force refresh to get fresh tokens and avoid 403 errors
    const session = await fetchAuthSession({ forceRefresh: true });
    const accessToken = session.tokens?.accessToken?.toString();
    
    if (!accessToken) {
      throw new Error('No valid access token found. Please ensure you are authenticated.');
    }

    console.log('Invoking agent core with query:', query);

    // URL encode the agent ARN
    const escapedAgentArn = encodeURIComponent(AGENT_CONFIG.AGENT_RUNTIME_ARN);
    
    // Construct the URL
    const url = `${BEDROCK_AGENT_CORE_ENDPOINT_URL}/runtimes/${escapedAgentArn}/invocations?qualifier=${AGENT_CONFIG.AGENT_ENDPOINT_NAME}`;

    // Generate a proper trace ID
    const traceId = `1-${Math.floor(Date.now() / 1000).toString(16)}-${generateId()}`;
    
    // Set up headers
    const headers = {
      "Authorization": `Bearer ${accessToken}`,
      "X-Amzn-Trace-Id": traceId,
      "Content-Type": "application/json",
      "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sessionId
    };

    // Create the payload
    const payload = {
      prompt: query,
      user_id: userId,
      session_id: sessionId
    };

    console.log('Agent Core Payload:', payload);

    // Make HTTP request with streaming
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });

    console.log(`Response Status: ${response.status}`);
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    let completion = '';
    let messageInitialized = false;
    let isCompleted = false;
    
    // Loop tracking variables
    let previousLoops: string[] = [];
    
    // Thinking detection variables
    let isInThinking = false;
    let thinkingContent = '';
    let regularContent = '';
    let endTagBuffer = '';
    
    // Tool/subagent tracking
    let currentToolUse = '';
    let subagentSteps: SubagentStep[] = [];
    let currentSubagentContent = '';

    // Initialize streaming output
    console.log('------- Agent Response (Streaming) -------');

    try {
      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            
            // Process complete lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
              if (!line.trim()) continue;
              
              try {
                // Handle Server-Sent Events format - strip "data: " prefix
                let jsonString = line;
                if (line.startsWith('data: ')) {
                  jsonString = line.substring(6);
                }
                
                // Skip [DONE] messages
                if (jsonString === '[DONE]') continue;
                
                // Skip noise (Python repr strings, control events)
                if (shouldSkipLine(jsonString)) continue;
                
                // Check for throttled delay event
                if (line.includes('event_loop_throttled_delay')) {
                  if (messageInitialized) {
                    setAnswers((prevState) => {
                      const newState = [...prevState];
                      for (let i = newState.length - 1; i >= 0; i--) {
                        if (newState[i].isStreaming) {
                          newState[i] = { ...newState[i], status: 'Server is busy' };
                          break;
                        }
                      }
                      return newState;
                    });
                  }
                  continue;
                }
                
                // Parse JSON
                let chunkData;
                try {
                  chunkData = JSON.parse(jsonString);
                } catch {
                  continue; // Skip non-JSON lines
                }
                
                // Skip if already completed
                if (isCompleted) continue;
                
                // Initialize message on first content
                if (!messageInitialized && (
                  chunkData.event?.contentBlockDelta?.delta?.text ||
                  chunkData.event?.messageStart ||
                  chunkData.event?.contentBlockStart?.start?.toolUse
                )) {
                  messageInitialized = true;
                  setAnswers((prevState) => [
                    ...prevState,
                    { 
                      id: generateId(),
                      role: 'assistant',
                      content: '', 
                      isStreaming: true,
                      status: 'Streaming...',
                      subagentSteps: []
                    },
                  ]);
                }
                
                // Handle text streaming (contentBlockDelta)
                if (chunkData.event?.contentBlockDelta?.delta?.text) {
                  const chunkText = chunkData.event.contentBlockDelta.delta.text;
                  completion += chunkText;
                  
                  // Thinking tag detection
                  if (chunkText.includes('<thinking') && !isInThinking) {
                    isInThinking = true;
                  }
                  
                  if (isInThinking) {
                    thinkingContent += chunkText;
                    endTagBuffer += chunkText;
                    if (endTagBuffer.includes('</thinking>')) {
                      isInThinking = false;
                      endTagBuffer = '';
                    }
                    if (endTagBuffer.length > 15) {
                      endTagBuffer = endTagBuffer.slice(-15);
                    }
                  } else {
                    regularContent += chunkText;
                  }
                  
                  setAnswers((prevState) => {
                    const newState = [...prevState];
                    for (let i = newState.length - 1; i >= 0; i--) {
                      if (newState[i].isStreaming) {
                        newState[i] = {
                          ...newState[i],
                          content: regularContent,
                          currentLoop: regularContent,
                          previousLoops: [...previousLoops],
                          thinkingContent: thinkingContent || undefined,
                          status: isInThinking ? 'Thinking...' : 'Streaming...'
                        };
                        break;
                      }
                    }
                    return newState;
                  });
                }
                
                // Handle tool call starting (contentBlockStart with toolUse)
                else if (chunkData.event?.contentBlockStart?.start?.toolUse) {
                  const toolUse = chunkData.event.contentBlockStart.start.toolUse;
                  currentToolUse = toolUse.name;
                  currentSubagentContent = '';
                  console.log(`Tool call starting: ${toolUse.name}`);
                  
                  setAnswers((prevState) => {
                    const newState = [...prevState];
                    for (let i = newState.length - 1; i >= 0; i--) {
                      if (newState[i].isStreaming) {
                        newState[i] = {
                          ...newState[i],
                          status: `Using ${toolUse.name}`,
                          currentSubagent: {
                            name: toolUse.name,
                            input: '',
                            content: ''
                          }
                        };
                        break;
                      }
                    }
                    return newState;
                  });
                }
                
                // Handle messageStop for loop transitions and completion
                else if (chunkData.event?.messageStop) {
                  if (chunkData.event.messageStop.stopReason !== 'end_turn') {
                    console.log('Loop transition detected - tool use cycle');
                    // Move current content to previous loops if there's content
                    if (regularContent.trim().length > 0) {
                      previousLoops.push(regularContent.trim());
                      regularContent = '';
                    }
                    
                    setAnswers((prevState) => {
                      const newState = [...prevState];
                      for (let i = newState.length - 1; i >= 0; i--) {
                        if (newState[i].isStreaming) {
                          newState[i] = {
                            ...newState[i],
                            content: regularContent,
                            currentLoop: regularContent,
                            previousLoops: [...previousLoops],
                            status: currentToolUse ? `Using ${currentToolUse}` : 'Processing...'
                          };
                          break;
                        }
                      }
                      return newState;
                    });
                  } else {
                    // Final completion
                    console.log('Message completion detected');
                    isCompleted = true;
                    
                    setAnswers((prevState) => {
                      const newState = [...prevState];
                      for (let i = newState.length - 1; i >= 0; i--) {
                        if (newState[i].isStreaming) {
                          newState[i] = {
                            ...newState[i],
                            content: regularContent,
                            currentLoop: regularContent,
                            previousLoops: [...previousLoops],
                            thinkingContent: thinkingContent || undefined,
                            subagentSteps: subagentSteps.length > 0 ? subagentSteps : undefined,
                            isStreaming: false,
                            status: 'complete'
                          };
                          break;
                        }
                      }
                      return newState;
                    });
                  }
                }
                
                // Handle tool_stream_event - subagent streaming
                else if (chunkData.tool_stream_event) {
                  const toolStreamEvent = chunkData.tool_stream_event;
                  const toolUseInfo = toolStreamEvent.tool_use;
                  const streamData = toolStreamEvent.data;
                  
                  // Update current tool if provided
                  if (toolUseInfo?.name && toolUseInfo.name !== currentToolUse) {
                    currentToolUse = toolUseInfo.name;
                  }
                  
                  // Handle streaming text from subagent
                  if (streamData?.data && typeof streamData.data === 'string') {
                    currentSubagentContent += streamData.data;
                    
                    setAnswers((prevState) => {
                      const newState = [...prevState];
                      for (let i = newState.length - 1; i >= 0; i--) {
                        if (newState[i].isStreaming) {
                          newState[i] = {
                            ...newState[i],
                            status: `${currentToolUse}: working...`,
                            currentSubagent: {
                              name: currentToolUse,
                              input: toolUseInfo?.input ? JSON.stringify(toolUseInfo.input) : '',
                              content: currentSubagentContent
                            }
                          };
                          break;
                        }
                      }
                      return newState;
                    });
                  }
                  
                  // Handle subagent result
                  if (streamData?.result) {
                    // Save completed subagent step
                    subagentSteps.push({
                      agentName: currentToolUse,
                      input: toolUseInfo?.input ? JSON.stringify(toolUseInfo.input) : '',
                      content: currentSubagentContent || String(streamData.result),
                      timestamp: Date.now()
                    });
                    
                    setAnswers((prevState) => {
                      const newState = [...prevState];
                      for (let i = newState.length - 1; i >= 0; i--) {
                        if (newState[i].isStreaming) {
                          newState[i] = {
                            ...newState[i],
                            subagentSteps: [...subagentSteps],
                            currentSubagent: undefined,
                            status: 'Processing result...'
                          };
                          break;
                        }
                      }
                      return newState;
                    });
                    
                    currentSubagentContent = '';
                  }
                }
                
                // Handle toolResult (for purchase confirmation and ui_actions detection)
                else if (chunkData.message?.content?.[0]?.toolResult) {
                  const toolResult = chunkData.message.content[0].toolResult;
                  if (toolResult.content && typeof toolResult.content === 'string') {
                    try {
                      const resultData = JSON.parse(toolResult.content);

                      // Check for purchase confirmation
                      if (resultData.requires_confirmation === true) {
                        console.log('Purchase confirmation required detected');
                        setAnswers((prevState) => {
                          const newState = [...prevState];
                          for (let i = newState.length - 1; i >= 0; i--) {
                            if (newState[i].isStreaming) {
                              newState[i] = {
                                ...newState[i],
                                purchaseConfirmation: resultData
                              };
                              break;
                            }
                          }
                          return newState;
                        });
                      }

                      // Check for ui_actions (agent-driven UI buttons)
                      if (resultData.ui_actions && Array.isArray(resultData.ui_actions)) {
                        console.log('UI actions detected:', resultData.ui_actions);
                        setAnswers((prevState) => {
                          const newState = [...prevState];
                          for (let i = newState.length - 1; i >= 0; i--) {
                            if (newState[i].isStreaming) {
                              newState[i] = {
                                ...newState[i],
                                ui_actions: resultData.ui_actions
                              };
                              break;
                            }
                          }
                          return newState;
                        });
                      }

                      // Check for card check result from check_user_has_payment_card tool
                      if (resultData.has_card !== undefined) {
                        console.log('Card check result detected:', resultData);
                        setAnswers((prevState) => {
                          const newState = [...prevState];
                          for (let i = newState.length - 1; i >= 0; i--) {
                            if (newState[i].isStreaming) {
                              newState[i] = {
                                ...newState[i],
                                card_check_result: {
                                  has_card: resultData.has_card,
                                  has_primary: resultData.has_primary,
                                  has_backup: resultData.has_backup,
                                  card_info: resultData.card_info || null
                                }
                              };
                              break;
                            }
                          }
                          return newState;
                        });
                      }
                    } catch {
                      // Not JSON or doesn't have metadata, continue
                    }
                  }
                }
                
              } catch (parseError) {
                console.error('Error parsing streaming chunk:', parseError);
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      } else {
        // Handle non-streaming response (fallback)
        const responseText = await response.text();
        completion = responseText;
        console.log('Agent Response Text (Non-streaming):', completion);

        setAnswers((prevState) => [
          ...prevState,
          { 
            id: generateId(),
            role: 'assistant',
            content: completion, 
            isStreaming: false,
            status: 'complete'
          },
        ]);
      }
    } catch (streamError) {
      console.error('Error processing agent response stream:', streamError);
      throw streamError;
    }

    // Ensure streaming is marked complete
    if (!isCompleted && messageInitialized) {
      setAnswers((prevState) => {
        const newState = [...prevState];
        for (let i = newState.length - 1; i >= 0; i--) {
          if (newState[i].isStreaming && newState[i].status !== 'complete') {
            newState[i] = {
              ...newState[i],
              isStreaming: false,
              status: 'complete'
            };
            break;
          }
        }
        return newState;
      });
    }

    console.log('------- End of Agent Response -------');
    
    return {
      sessionId: sessionId,
      completion,
    };
  } catch (error) {
    console.error('Error invoking agent core:', error);
    
    setAnswers((prevState) => [
      ...prevState,
      {
        id: generateId(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your message. Please try again.',
        isStreaming: false,
      },
    ]);
    
    throw error;
  }
};

/**
 * Get current agent configuration
 */
export const getCurrentAgentConfig = () => AGENT_CONFIG;

/**
 * Update agent configuration (for runtime configuration)
 */
export const updateAgentConfig = (newConfig: Partial<typeof AGENT_CONFIG>) => {
  Object.assign(AGENT_CONFIG, newConfig);
};
