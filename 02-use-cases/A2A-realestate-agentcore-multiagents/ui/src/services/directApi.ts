import axios from 'axios';

// Load configuration from environment or config file
const BEARER_TOKEN = process.env.REACT_APP_BEARER_TOKEN || '';
const COORDINATOR_AGENT_ARN = process.env.REACT_APP_COORDINATOR_AGENT_ARN || '';

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
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

async function callAgent(agentArn: string, message: string): Promise<string> {
  const url = getAgentUrl(agentArn);
  const sessionId = generateUUID();
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
      'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId
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
    throw new Error('Configuration missing. Please set REACT_APP_BEARER_TOKEN and REACT_APP_COORDINATOR_AGENT_ARN.');
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
