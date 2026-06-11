import axios from 'axios';

// Load configuration from environment or config file
const BEARER_TOKEN = import.meta.env.VITE_BEARER_TOKEN || '';
const COORDINATOR_AGENT_ARN = import.meta.env.VITE_COORDINATOR_AGENT_ARN || '';

// Persistent session ID for conversation context
let CONVERSATION_SESSION_ID: string | null = null;

export interface AgentResponse {
  success: boolean;
  response: string;
  timestamp: string;
  error?: string;
}

function getAgentUrl(arn: string): string {
  const arnEncoded = arn.replace(/:/g, '%3A').replace(/\//g, '%2F');
  return `https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/${arnEncoded}/invocations/`;
}

function generateUUID(): string {
  // Use crypto.randomUUID() if available (modern browsers)
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  
  // Fallback to crypto.getRandomValues
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    
    // Set version (4) and variant bits
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    
    const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  
  throw new Error('No secure random number generator available. Please use a modern browser.');
}

async function callAgent(agentArn: string, message: string): Promise<string> {
  const url = getAgentUrl(agentArn);
  
  // Use persistent session ID for conversation continuity
  if (!CONVERSATION_SESSION_ID) {
    CONVERSATION_SESSION_ID = generateUUID();
    console.log('🔑 New conversation session started:', CONVERSATION_SESSION_ID);
  }
  
  const messageId = generateUUID();
  
  const jsonrpcRequest = {
    jsonrpc: '2.0',
    id: `req-${generateUUID().substring(0, 8)}`,
    method: 'message/send',
    params: {
      message: {
        role: 'user',
        parts: [{ kind: 'text', text: message }],
        messageId: messageId
      }
    }
  };
  
  const response = await axios.post(url, jsonrpcRequest, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${BEARER_TOKEN}`,
      'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': CONVERSATION_SESSION_ID
    },
    timeout: 120000 // 2 minutes
  });
  
  if (response.data.result && response.data.result.artifacts) {
    const artifacts = response.data.result.artifacts;
    if (artifacts.length > 0 && artifacts[0].parts) {
      return artifacts[0].parts[0].text || 'No response';
    }
  }
  
  return JSON.stringify(response.data);
}

export const checkHealth = async (): Promise<{ status: string; timestamp: string }> => {
  // Check if token and coordinator ARN are configured
  if (!BEARER_TOKEN || !COORDINATOR_AGENT_ARN) {
    throw new Error('Configuration missing. Please set VITE_BEARER_TOKEN and VITE_COORDINATOR_AGENT_ARN.');
  }
  
  return {
    status: 'healthy',
    timestamp: new Date().toISOString()
  };
};

export const sendMessage = async (message: string): Promise<AgentResponse> => {
  try {
    // Send all messages to coordinator agent
    // Coordinator will orchestrate sub-agents using A2A protocol
    if (!COORDINATOR_AGENT_ARN) {
      throw new Error('Coordinator agent ARN not configured');
    }
    
    const responseText = await callAgent(COORDINATOR_AGENT_ARN, message);
    
    return {
      success: true,
      response: responseText,
      timestamp: new Date().toISOString()
    };
  } catch (error: any) {
    return {
      success: false,
      response: '',
      timestamp: new Date().toISOString(),
      error: error.message || 'Failed to communicate with coordinator agent'
    };
  }
};
