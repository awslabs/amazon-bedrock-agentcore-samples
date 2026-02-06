export interface ChatRequest {
  message: string;
  conversationId?: string;
  sessionId?: string;
}

export interface ChatResponse {
  response: string;
  conversationId: string;
  sessionId?: string;
}

export interface AgentCoreEvent {
  actionGroup: string;
  apiPath: string;
  parameters: Record<string, any>;
  sessionId?: string;
}

export interface AgentCoreResponse {
  statusCode: number;
  body: any;
}
