/**
 * Authentication service for getting bearer tokens
 * Mimics the behavior of test/connect_agent.py get_bearer_token() (lines 276-289)
 */

/**
 * Get bearer token using OAuth2 client credentials flow
 * This requires Cognito client ID and secret configured in environment
 */
export async function getBearerToken(): Promise<string> {
  const tokenEndpoint = import.meta.env.VITE_COGNITO_TOKEN_ENDPOINT;
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const clientSecret = import.meta.env.VITE_COGNITO_CLIENT_SECRET;

  if (!tokenEndpoint || !clientId || !clientSecret) {
    throw new Error('Cognito configuration missing. Please set VITE_COGNITO_TOKEN_ENDPOINT, VITE_COGNITO_CLIENT_ID, and VITE_COGNITO_CLIENT_SECRET in .env file');
  }

  // Create Basic Auth header (client_id:client_secret encoded in base64)
  const credentials = btoa(`${clientId}:${clientSecret}`);

  try {
    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': `Basic ${credentials}`,
      },
      body: new URLSearchParams({
        grant_type: 'client_credentials',
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get bearer token: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    return data.access_token;
  } catch (error) {
    console.error('Error getting bearer token:', error);
    throw error;
  }
}
