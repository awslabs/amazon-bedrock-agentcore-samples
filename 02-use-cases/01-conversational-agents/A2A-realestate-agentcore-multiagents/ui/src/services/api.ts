import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 minutes timeout for agent responses
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ChatResponse {
  success: boolean;
  response: string;
  timestamp: string;
  error?: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
}

export interface ConfigResponse {
  success: boolean;
  config: {
    user_pool_id: string;
    agents: string[];
  };
}

export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
};

export const getConfig = async (): Promise<ConfigResponse> => {
  const response = await api.get<ConfigResponse>('/config');
  return response.data;
};

export const sendMessage = async (message: string): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>('/chat', { message });
  
  if (!response.data.success) {
    throw new Error(response.data.error || 'Failed to get response from agent');
  }
  
  return response.data;
};

export const refreshToken = async (): Promise<void> => {
  await api.post('/token/refresh');
};

export default api;
