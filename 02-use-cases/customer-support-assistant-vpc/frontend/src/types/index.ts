export interface Message {
  role: 'user' | 'assistant';
  content: string;
  elapsed?: number;
  timestamp?: number;
}

export interface TokenResponse {
  access_token: string;
  id_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export interface UserClaims {
  sub: string;
  email: string;
  'cognito:username': string;
  email_verified: boolean;
  aud: string;
  token_use: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  tokens: TokenResponse | null;
  userClaims: UserClaims | null;
  loading: boolean;
  error: string | null;
}

export interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  sessionId: string;
  agentArn: string;
  region: string;
}

export interface AppConfig {
  stackName: string;
  cognitoDomain: string;
  clientId: string;
  redirectUri: string;
  scopes: string;
}
