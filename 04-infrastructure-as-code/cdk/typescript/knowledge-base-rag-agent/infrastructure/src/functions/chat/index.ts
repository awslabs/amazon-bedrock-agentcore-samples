import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { DynamoDBClient, PutItemCommand, QueryCommand } from '@aws-sdk/client-dynamodb';
import { Logger } from '@aws-lambda-powertools/logger';
import { randomBytes } from 'crypto';

// Initialize logger for security audit trails
const logger = new Logger({ serviceName: 'chat-service' });

// Define types locally
interface ChatRequest {
  message: string;
  sessionId?: string;
}

interface ChatResponse {
  response: string;
  conversationId: string;
  sessionId: string;
}

interface AuthContext {
  userId: string;
  email?: string;
}

// Security validation errors
class AuthorizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthorizationError';
  }
}

class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

// Initialize AWS SDK clients
const dynamoClient = new DynamoDBClient({ region: process.env.AWS_REGION });

/**
 * Extract and validate user context from Cognito JWT claims
 * This prevents IDOR attacks by ensuring users can only access their own data
 */
function extractUserContext(event: APIGatewayProxyEvent): AuthContext {
  const userId = event.requestContext.authorizer?.claims?.sub;
  const email = event.requestContext.authorizer?.claims?.email;
  
  if (!userId) {
    logger.error('Missing user ID in JWT claims', {
      requestId: event.requestContext.requestId,
      claims: event.requestContext.authorizer?.claims
    });
    throw new AuthorizationError('Invalid authentication token - missing user ID');
  }
  
  logger.info('User authenticated', {
    userId: userId.substring(0, 8) + '...',
    email: email ? email.replace(/(.{2}).*(@.*)/, '$1***$2') : undefined,
    requestId: event.requestContext.requestId
  });
  
  return { userId, email };
}

/**
 * Validate that a session belongs to the authenticated user
 */
async function validateSessionOwnership(sessionId: string, userId: string): Promise<boolean> {
  try {
    const result = await dynamoClient.send(
      new QueryCommand({
        TableName: process.env.SESSIONS_TABLE!,
        KeyConditionExpression: 'sessionId = :sessionId',
        FilterExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':sessionId': { S: sessionId },
          ':userId': { S: userId }
        },
        Limit: 1
      })
    );
    
    return !!(result.Items && result.Items.length > 0);
  } catch (error) {
    logger.error('Error validating session ownership', {
      sessionId: sessionId.substring(0, 8) + '...',
      userId: userId.substring(0, 8) + '...',
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    return false;
  }
}

/**
 * Sanitize input to prevent injection attacks and log exposure
 */
function sanitizeInput(input: string): string {
  // Remove control characters, mask PII patterns
  return input
    .replace(/[\u0000-\u001F\u007F]/g, '') // Control characters
    .replace(/\b\d{3}-\d{2}-\d{4}\b/g, '[SSN]')
    .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, '[EMAIL]')
    .replace(/\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g, '[CARD]')
    .trim();
}

/**
 * Invoke AgentCore Runtime using Bearer token authentication
 * Based on AWS documentation: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html
 * 
 * When AgentCore Runtime is configured with Cognito authentication, we pass the
 * user's Cognito access token as a Bearer token instead of using SigV4 signing.
 */
async function invokeAgentCoreRuntime(
  runtimeArn: string,
  sessionId: string,
  payload: { prompt: string; session_id: string; user_id: string },
  bearerToken: string
): Promise<string> {
  const region = process.env.AWS_REGION || 'us-east-1';
  
  // Build the request URL for AgentCore Runtime
  // Format: https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtimeArn}/invocations
  // See: https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_InvokeAgentRuntime.html
  const host = `bedrock-agentcore.${region}.amazonaws.com`;
  const path = `/runtimes/${encodeURIComponent(runtimeArn)}/invocations`;
  
  const body = JSON.stringify(payload);
  
  // Make the HTTP request with Bearer token authentication
  // AgentCore Runtime configured with Cognito expects the user's access token
  const response = await fetch(`https://${host}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Authorization': `Bearer ${bearerToken}`,
      'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId,
    },
    body: body,
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    logger.error('AgentCore Runtime invocation failed', {
      status: response.status,
      statusText: response.statusText,
      error: errorText,
    });
    throw new Error(`AgentCore Runtime invocation failed: ${response.status} ${response.statusText}`);
  }
  
  // Handle streaming response
  const contentType = response.headers.get('content-type') || '';
  
  if (contentType.includes('text/event-stream')) {
    // Handle Server-Sent Events (SSE) streaming response
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }
    
    const decoder = new TextDecoder();
    let fullResponse = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.substring(6);
          try {
            const parsed = JSON.parse(data);
            if (parsed.response) {
              fullResponse += parsed.response;
            } else if (parsed.text) {
              fullResponse += parsed.text;
            } else if (typeof parsed === 'string') {
              fullResponse += parsed;
            }
          } catch {
            // If not JSON, append as-is
            fullResponse += data;
          }
        }
      }
    }
    
    return fullResponse;
  } else {
    // Handle standard JSON response
    const responseData = await response.json();
    return responseData.response || responseData.result || JSON.stringify(responseData);
  }
}

/**
 * Get chat history for the authenticated user
 */
async function getChatHistory(userId: string, sessionId?: string): Promise<unknown[]> {
  try {
    let queryParams;
    
    if (sessionId) {
      const isValidSession = await validateSessionOwnership(sessionId, userId);
      if (!isValidSession) {
        throw new AuthorizationError('Access denied - session not found or unauthorized');
      }
      
      queryParams = {
        TableName: process.env.CHAT_HISTORY_TABLE || 'AgentCore-ChatHistory',
        KeyConditionExpression: 'sessionId = :sessionId',
        ExpressionAttributeValues: {
          ':sessionId': { S: sessionId }
        },
        ScanIndexForward: true,
        Limit: 50
      };
    } else {
      queryParams = {
        TableName: process.env.CHAT_HISTORY_TABLE || 'AgentCore-ChatHistory',
        IndexName: 'UserIdIndex',
        KeyConditionExpression: 'userId = :userId',
        ExpressionAttributeValues: {
          ':userId': { S: userId }
        },
        ScanIndexForward: false,
        Limit: 20
      };
    }
    
    const result = await dynamoClient.send(new QueryCommand(queryParams));
    return result.Items || [];
  } catch (error) {
    logger.error('Error retrieving chat history', {
      userId: userId.substring(0, 8) + '...',
      sessionId: sessionId ? sessionId.substring(0, 8) + '...' : undefined,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    throw error;
  }
}

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const requestId = event.requestContext.requestId;
  
  try {
    const userContext = extractUserContext(event);
    
    // Handle GET requests for chat history
    if (event.httpMethod === 'GET') {
      const sessionId = event.queryStringParameters?.sessionId;
      
      logger.info('Retrieving chat history', {
        userId: userContext.userId.substring(0, 8) + '...',
        sessionId: sessionId ? sessionId.substring(0, 8) + '...' : 'all',
        requestId
      });
      
      const history = await getChatHistory(userContext.userId, sessionId);
      
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
          'Access-Control-Allow-Headers': 'Content-Type'
        },
        body: JSON.stringify({ history }),
      };
    }
    
    // Handle POST requests for chat
    if (event.httpMethod !== 'POST') {
      throw new ValidationError('Method not allowed');
    }
    
    const body: ChatRequest = JSON.parse(event.body || '{}');
    const { message, sessionId } = body;
    
    if (!message || typeof message !== 'string') {
      throw new ValidationError('Message is required and must be a string');
    }
    
    if (message.length > 4000) {
      throw new ValidationError('Message too long (max 4000 characters)');
    }
    
    const sanitizedMessage = sanitizeInput(message);
    
    logger.info('Processing chat request', {
      userId: userContext.userId.substring(0, 8) + '...',
      messageLength: sanitizedMessage.length,
      sessionId: sessionId ? sessionId.substring(0, 8) + '...' : 'new',
      requestId
    });

    // Generate user-scoped session ID if not provided
    let currentSessionId: string;
    
    if (sessionId) {
      const isValidSession = await validateSessionOwnership(sessionId, userContext.userId);
      if (!isValidSession) {
        logger.warn('Unauthorized session access attempt', {
          userId: userContext.userId.substring(0, 8) + '...',
          sessionId: sessionId.substring(0, 8) + '...',
          requestId
        });
        throw new AuthorizationError('Access denied - session not found or unauthorized');
      }
      currentSessionId = sessionId;
    } else {
      // Use cryptographically secure random bytes for session ID generation
      currentSessionId = `${userContext.userId}-${Date.now()}-${randomBytes(8).toString('hex')}`;
    }

    logger.info('Invoking AgentCore Runtime', {
      userId: userContext.userId.substring(0, 8) + '...',
      sessionId: currentSessionId.substring(0, 8) + '...',
      requestId
    });
    
    // Invoke AgentCore Runtime with Bearer token authentication
    // Frontend sends two tokens:
    // - Authorization header: ID token (validated by API Gateway Cognito authorizer)
    // - X-AgentCore-Token header: Access token (validated by AgentCore Runtime)
    const accessToken = event.headers['X-AgentCore-Token'] || event.headers['x-agentcore-token'];
    if (!accessToken) {
      throw new AuthorizationError('Missing X-AgentCore-Token header');
    }
    
    // Use the access token for AgentCore Runtime (it validates 'client_id' claim)
    const bearerToken = accessToken;
    
    // Debug: decode and log token claims (without signature verification)
    try {
      const tokenParts = bearerToken.split('.');
      if (tokenParts.length === 3) {
        const payload = JSON.parse(Buffer.from(tokenParts[1], 'base64').toString('utf-8'));
        logger.info('Token claims', {
          token_use: payload.token_use,
          client_id: payload.client_id,
          aud: payload.aud,
          iss: payload.iss,
          requestId
        });
      }
    } catch (e) {
      logger.warn('Could not decode token for debugging', { error: (e as Error).message });
    }
    
    const runtimeArn = process.env.AGENTCORE_RUNTIME_ARN!;
    
    const responseText = await invokeAgentCoreRuntime(runtimeArn, currentSessionId, {
      prompt: message,
      session_id: currentSessionId,
      user_id: userContext.userId,
    }, bearerToken);

    // Store session information in DynamoDB
    await dynamoClient.send(
      new PutItemCommand({
        TableName: process.env.SESSIONS_TABLE!,
        Item: {
          sessionId: { S: currentSessionId },
          userId: { S: userContext.userId },
          lastMessage: { S: sanitizedMessage },
          lastResponse: { S: responseText },
          timestamp: { N: Date.now().toString() },
          email: userContext.email ? { S: userContext.email } : { NULL: true },
        },
      })
    );

    logger.info('Chat request processed successfully', {
      userId: userContext.userId.substring(0, 8) + '...',
      sessionId: currentSessionId.substring(0, 8) + '...',
      responseLength: responseText.length,
      requestId
    });
    
    const finalResponse = responseText || 'I received your message but was unable to generate a response. Please try again.';
    
    const response: ChatResponse = {
      response: finalResponse,
      conversationId: currentSessionId,
      sessionId: currentSessionId,
    };

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        'Access-Control-Allow-Headers': 'Content-Type'
      },
      body: JSON.stringify(response),
    };

  } catch (error) {
    logger.error('Error processing chat request', {
      error: error instanceof Error ? error.message : 'Unknown error',
      errorType: error instanceof Error ? error.constructor.name : 'Unknown',
      requestId,
    });
    
    if (error instanceof AuthorizationError) {
      return {
        statusCode: 403,
        headers: { 
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
          'Access-Control-Allow-Headers': 'Content-Type'
        },
        body: JSON.stringify({ 
          error: 'Access denied',
          message: error.message
        }),
      };
    }
    
    if (error instanceof ValidationError) {
      return {
        statusCode: 400,
        headers: { 
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
          'Access-Control-Allow-Headers': 'Content-Type'
        },
        body: JSON.stringify({ 
          error: 'Invalid request',
          message: error.message
        }),
      };
    }
    
    return {
      statusCode: 500,
      headers: { 
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        'Access-Control-Allow-Headers': 'Content-Type'
      },
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: 'An unexpected error occurred while processing your request'
      }),
    };
  }
};
