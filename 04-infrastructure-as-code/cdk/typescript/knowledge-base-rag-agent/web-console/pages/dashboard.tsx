import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Button,
  Container,
} from '@mui/material';
import {
  Chat as ChatIcon,
} from '@mui/icons-material';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

const Dashboard: React.FC = () => {
  const router = useRouter();

  // Handle navigation to chat
  const handleStartChat = () => {
    router.push('/chat');
  };

  return (
    <Layout>
      <Container maxWidth="lg">
        <Box sx={{ mt: 4, mb: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            AgentCore Dashboard
          </Typography>
          <Typography variant="subtitle1" color="text.secondary" paragraph>
            Welcome to your AI-powered assistant. Start a conversation to get help with your questions.
          </Typography>

          <Grid container spacing={3} sx={{ mt: 2 }}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent sx={{ textAlign: 'center', py: 4 }}>
                  <ChatIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
                  <Typography variant="h5" component="h2" gutterBottom>
                    Chat with AI Assistant
                  </Typography>
                  <Typography variant="body1" color="text.secondary" paragraph>
                    Start a conversation with your Bedrock-powered AI assistant. 
                    Ask questions, get help, and explore what the agent can do for you.
                  </Typography>
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<ChatIcon />}
                    onClick={handleStartChat}
                    sx={{ mt: 2 }}
                  >
                    Start Chat
                  </Button>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent sx={{ py: 4 }}>
                  <Typography variant="h6" component="h3" gutterBottom>
                    Features
                  </Typography>
                  <Box component="ul" sx={{ pl: 2 }}>
                    <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                      Natural language conversations
                    </Typography>
                    <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                      Knowledge base integration
                    </Typography>
                    <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                      Session management
                    </Typography>
                    <Typography component="li" variant="body2" sx={{ mb: 1 }}>
                      Real-time responses
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      </Container>
    </Layout>
  );
};

export default Dashboard;