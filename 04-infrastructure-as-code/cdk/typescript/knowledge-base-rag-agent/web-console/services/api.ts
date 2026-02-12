import { getApiUrl } from '../utils/config';

export interface ChatMessage {
  message: string;
  conversationId?: string;
}

export interface ChatResponse {
  response: string;
  conversationId: string;
}

export const chatApi = {
  async sendMessage(message: ChatMessage): Promise<ChatResponse> {
    const apiUrl = await getApiUrl();
    
    // Get auth token
    const { fetchAuthSession } = await import('aws-amplify/auth');
    const session = await fetchAuthSession();
    const token = session.tokens?.idToken?.toString();
    
    const response = await fetch(`${apiUrl}/chat/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(message),
    });

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    return response.json();
  },
};
