/**
 * Simple Chat Interface for AgentCore
 * 
 * This component demonstrates the basic pattern for building a chat interface
 * that interacts with an AgentCore agent through a REST API.
 * 
 * Key features:
 * - Send messages to the agent
 * - Display conversation history
 * - Handle loading states and errors
 * - Session management
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  CircularProgress,
  Card,
  CardContent,
  Alert,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import DeleteIcon from '@mui/icons-material/Delete';
import Layout from '../components/Layout';
import { sanitizeInput, validateChatInput } from '../utils/validation';

// Simple interfaces for type safety
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatResponse {
  response: string;
  sessionId: string;
}

const Chat: React.FC = () => {
  // Component state for managing the chat interface
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Auto-scroll to bottom when new messages are added
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize the chat with a welcome message
  useEffect(() => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: "Hello! I'm your AI assistant. How can I help you today?",
        timestamp: new Date(),
      },
    ]);
  }, []);

  // Send a message to the AgentCore agent
  const sendMessage = async (message: string) => {
    setIsLoading(true);
    setError(null);

    try {
      // Get API URL from config
      const { getApiUrl } = await import('../utils/config');
      const apiUrl = await getApiUrl();
      
      // Get auth tokens:
      // - ID token for API Gateway Cognito authorizer (validates 'aud' claim)
      // - Access token for AgentCore Runtime (validates 'client_id' claim)
      const { fetchAuthSession } = await import('aws-amplify/auth');
      const session = await fetchAuthSession();
      const idToken = session.tokens?.idToken?.toString();
      const accessToken = session.tokens?.accessToken?.toString();

      // Send request to the chat API
      const response = await fetch(`${apiUrl}/chat/invoke`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(idToken ? { 'Authorization': `Bearer ${idToken}` } : {}),
          ...(accessToken ? { 'X-AgentCore-Token': accessToken } : {}),
        },
        body: JSON.stringify({
          message,
          sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ChatResponse = await response.json();

      // Check if component is still mounted before updating state
      if (!mountedRef.current) return;

      // Update session ID if provided
      if (data.sessionId && data.sessionId !== sessionId) {
        setSessionId(data.sessionId);
      }

      // Add assistant's response to the conversation
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response || "I apologize, but I couldn't process your request.",
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (err) {
      // Check if component is still mounted before updating state
      if (!mountedRef.current) return;

      console.error('Error sending message:', err);
      setError('Failed to send message. Please try again.');
      
      // Add error message to chat
      setMessages(prev => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: 'I apologize, but I encountered an error. Please try again.',
          timestamp: new Date(),
        },
      ]);
    } finally {
      // Check if component is still mounted before updating state
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  };

  // Handle sending a message
  const handleSendMessage = async () => {
    if (isLoading) return;

    // Validate input
    const validation = validateChatInput(input);
    if (!validation.valid) {
      setError(validation.error || 'Invalid input');
      return;
    }

    // Sanitize input
    const sanitized = sanitizeInput(input);

    // Add user message to the conversation
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: sanitized,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput(''); // Clear input immediately for better UX

    // Send the sanitized message to the agent
    await sendMessage(sanitized);
  };

  // Clear the chat history
  const handleClearChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: "Hello! I'm your AI assistant. How can I help you today?",
        timestamp: new Date(),
      },
    ]);
    setSessionId(null);
    setError(null);
  };

  // Handle Enter key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Layout title="AgentCore Chat">
      <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
        {/* Header Card */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              AgentCore Demo
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This is a simple chat interface that demonstrates how to interact with an AgentCore agent.
              The agent has access to a knowledge base and can answer questions based on the documents you provide.
            </Typography>
          </CardContent>
        </Card>

        {/* Error Display */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Chat Messages */}
        <Paper
          elevation={3}
          sx={{
            flexGrow: 1,
            p: 2,
            mb: 2,
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: 'calc(100vh - 280px)',
          }}
        >
          {messages.map(message => (
            <Box
              key={message.id}
              sx={{
                display: 'flex',
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                mb: 2,
              }}
            >
              <Paper
                elevation={1}
                sx={{
                  p: 2,
                  maxWidth: '80%',
                  backgroundColor: message.role === 'user' ? 'primary.light' : 'grey.100',
                  color: message.role === 'user' ? 'primary.contrastText' : 'text.primary',
                  borderRadius: 2,
                }}
              >
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                  {message.content}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ mt: 1, display: 'block' }}
                >
                  {message.timestamp.toLocaleTimeString()}
                </Typography>
              </Paper>
            </Box>
          ))}
          
          {/* Loading indicator */}
          {isLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}
          
          <div ref={messagesEndRef} />
        </Paper>

        {/* Input Area */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Type your message..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            multiline
            maxRows={3}
          />
          <Button
            variant="contained"
            color="primary"
            endIcon={<SendIcon />}
            onClick={handleSendMessage}
            disabled={isLoading || !input.trim()}
          >
            Send
          </Button>
          <Button
            variant="outlined"
            color="secondary"
            endIcon={<DeleteIcon />}
            onClick={handleClearChat}
            disabled={isLoading}
          >
            Clear
          </Button>
        </Box>
      </Box>
    </Layout>
  );
};

export default Chat;
