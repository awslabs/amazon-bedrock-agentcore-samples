// Utility to load configuration from config.json
let configCache: any = null;

export const loadConfig = async (): Promise<any> => {
  if (configCache) {
    return configCache;
  }

  try {
    const response = await fetch('/config.json');
    const config = await response.json();
    configCache = config;
    return config;
  } catch (error) {
    console.error('Failed to load config.json:', error);
    // Fallback to environment variables
    return {
      apiUrl: process.env.NEXT_PUBLIC_BEDROCK_AGENT_API_URL || process.env.NEXT_PUBLIC_API_ENDPOINT,
      userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID,
      userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_WEB_CLIENT_ID,
      identityPoolId: process.env.NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID,
      region: process.env.NEXT_PUBLIC_COGNITO_REGION || 'us-east-1',
    };
  }
};

export const getApiUrl = async (): Promise<string> => {
  const config = await loadConfig();
  return config.NEXT_PUBLIC_BEDROCK_AGENT_API_URL || config.apiUrl || 'https://fcozro5za9.execute-api.us-east-1.amazonaws.com/v1';
};