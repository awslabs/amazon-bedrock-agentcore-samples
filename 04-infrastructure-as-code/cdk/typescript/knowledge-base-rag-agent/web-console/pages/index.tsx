import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { getCurrentUser } from 'aws-amplify/auth';
import {
  CircularProgress,
  Box,
  Typography,
  Button,
  Container,
  Card,
  CardContent,
} from '@mui/material';

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is authenticated
    const checkAuth = async () => {
      try {
        await getCurrentUser();
        // If authenticated, redirect to dashboard
        router.push('/dashboard');
      } catch {
        // If not authenticated, just show the login button
        setLoading(false);
      }
    };

    // Add a timeout to ensure the page renders even if Auth has issues
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 3000);

    checkAuth();

    return () => clearTimeout(timeout);
  }, [router]);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          bgcolor: '#f5f5f5',
        }}
      >
        <Typography variant="h4" component="h1" gutterBottom>
          AgentCore Assistant
        </Typography>
        <CircularProgress />
        <Typography variant="body1" sx={{ mt: 2 }}>
          Loading...
        </Typography>
      </Box>
    );
  }

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          py: 4,
        }}
      >
        <Typography variant="h3" component="h1" gutterBottom sx={{ mb: 4 }}>
          AgentCore Assistant
        </Typography>

        <Card sx={{ width: '100%', mb: 4 }}>
          <CardContent>
            <Typography variant="h5" component="h2" gutterBottom>
              Welcome to your AI Assistant
            </Typography>
            <Typography variant="body1" paragraph>
              This application provides an intelligent chat interface powered by Amazon Bedrock.
              Start a conversation with your AI assistant to get help, ask questions, and explore
              what the agent can do for you.
            </Typography>

            <Typography variant="h6" component="h3" gutterBottom sx={{ mt: 2 }}>
              Features:
            </Typography>
            <ul>
              <li>
                <Typography variant="body1">
                  <strong>Natural Language Chat:</strong> Communicate with your AI assistant using
                  natural language conversations
                </Typography>
              </li>
              <li>
                <Typography variant="body1">
                  <strong>Knowledge Base Integration:</strong> Access information from integrated
                  knowledge sources and documents
                </Typography>
              </li>
              <li>
                <Typography variant="body1">
                  <strong>Session Management:</strong> Maintain conversation context across
                  multiple interactions
                </Typography>
              </li>
              <li>
                <Typography variant="body1">
                  <strong>Real-time Responses:</strong> Get immediate responses powered by
                  Amazon Bedrock's advanced AI capabilities
                </Typography>
              </li>
            </ul>

            <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
              <Button
                variant="contained"
                color="primary"
                size="large"
                onClick={() => router.push('/login')}
                sx={{ px: 4, py: 1.5, fontSize: '1.1rem' }}
              >
                Sign In
              </Button>
            </Box>
          </CardContent>
        </Card>


      </Box>
    </Container>
  );
}
