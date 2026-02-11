import { useEffect, useState } from 'react';
import type { AppProps } from 'next/app';
import { Amplify } from 'aws-amplify';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../contexts/AuthContext';
import ErrorBoundary from '../components/ErrorBoundary';
import '../styles/globals.css';

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

// Create a theme instance
const theme = createTheme({
  palette: {
    primary: {
      main: '#0073bb',
    },
    secondary: {
      main: '#ff9900',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
      '"Apple Color Emoji"',
      '"Segoe UI Emoji"',
      '"Segoe UI Symbol"',
    ].join(','),
  },
});

function MyApp({ Component, pageProps }: AppProps) {
  const [amplifyConfigured, setAmplifyConfigured] = useState(false);

  useEffect(() => {
    // Configure Amplify on client-side only
    if (typeof window !== 'undefined') {
      // Load configuration from config.json (deployed by CDK)
      fetch('/config.json')
        .then(response => response.json())
        .then(config => {
          const cognitoConfig = {
            region: config.NEXT_PUBLIC_COGNITO_REGION || config.region || 'us-east-1',
            userPoolId: config.NEXT_PUBLIC_COGNITO_USER_POOL_ID || config.userPoolId,
            userPoolWebClientId: config.NEXT_PUBLIC_COGNITO_USER_POOL_WEB_CLIENT_ID || config.userPoolClientId,
            identityPoolId: config.NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID || config.identityPoolId,
          };

          console.log('Configuring Amplify with:', {
            ...cognitoConfig,
            bedrockAgentApiUrl: config.NEXT_PUBLIC_BEDROCK_AGENT_API_URL || config.apiUrl,
          });

          // Check if we have the required Cognito configuration
          if (!cognitoConfig.userPoolId || !cognitoConfig.userPoolWebClientId) {
            console.warn('Missing Cognito configuration. Authentication will not work properly.');
            console.warn('Config loaded:', config);
            setAmplifyConfigured(true); // Still set to true to render the app
            return;
          }

          const amplifyConfig: any = {
            Auth: {
              Cognito: {
                userPoolId: cognitoConfig.userPoolId,
                userPoolClientId: cognitoConfig.userPoolWebClientId,
              },
            },
            API: {
              REST: {
                AgentCoreApi: {
                  endpoint: config.NEXT_PUBLIC_BEDROCK_AGENT_API_URL || config.apiUrl || 'https://fcozro5za9.execute-api.us-east-1.amazonaws.com/v1',
                  region: cognitoConfig.region,
                },
              },
            },
          };

          // Add identityPoolId only if it exists
          if (cognitoConfig.identityPoolId) {
            amplifyConfig.Auth.Cognito.identityPoolId = cognitoConfig.identityPoolId;
          }

          Amplify.configure(amplifyConfig);
          setAmplifyConfigured(true);
        })
        .catch(error => {
          console.error('Failed to load config.json:', error);
          console.warn('Falling back to environment variables');
          
          // Fallback to environment variables
          const cognitoConfig = {
            region: process.env.NEXT_PUBLIC_COGNITO_REGION || 'us-east-1',
            userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID,
            userPoolWebClientId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_WEB_CLIENT_ID,
            identityPoolId: process.env.NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID,
          };

          if (cognitoConfig.userPoolId && cognitoConfig.userPoolWebClientId) {
            const amplifyConfig: any = {
              Auth: {
                Cognito: {
                  userPoolId: cognitoConfig.userPoolId,
                  userPoolClientId: cognitoConfig.userPoolWebClientId,
                },
              },
              API: {
                REST: {
                  AgentCoreApi: {
                    endpoint: process.env.NEXT_PUBLIC_BEDROCK_AGENT_API_URL || 'https://fcozro5za9.execute-api.us-east-1.amazonaws.com/v1',
                    region: cognitoConfig.region,
                  },
                },
              },
            };

            // Add identityPoolId only if it exists
            if (cognitoConfig.identityPoolId) {
              amplifyConfig.Auth.Cognito.identityPoolId = cognitoConfig.identityPoolId;
            }

            Amplify.configure(amplifyConfig);
          }
          setAmplifyConfigured(true);
        });
    } else {
      // On server-side, just set configured to true
      setAmplifyConfigured(true);
    }
  }, []);

  // Show loading until Amplify is configured
  if (!amplifyConfigured) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        fontFamily: 'Arial, sans-serif'
      }}>
        Loading...
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <AuthProvider>
            <Component {...pageProps} />
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default MyApp;
