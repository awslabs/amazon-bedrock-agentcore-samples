import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import ChatMessage from './components/ChatMessage';
import { sendMessage, checkHealth } from './services/api';
import * as directApi from './services/directApi';

// Check if using direct API mode
const API_MODE = process.env.REACT_APP_API_MODE || 'proxy';
const api = API_MODE === 'direct' ? directApi : { sendMessage, checkHealth };

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Check API health on mount
    api.checkHealth()
      .then(() => setIsConnected(true))
      .catch(() => setIsConnected(false));

    // Add welcome message
    setMessages([{
      id: '1',
      text: "Hello! I'm your Real Estate Agent (A2A) powered by Amazon Bedrock AgentCore. I can help you search for properties and make bookings. What are you looking for today?",
      sender: 'agent',
      timestamp: new Date()
    }]);
  }, []);

  useEffect(() => {
    // Scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputValue,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await api.sendMessage(inputValue);
      
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response,
        sender: 'agent',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, agentMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        sender: 'agent',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickActions = [
    "Find apartments in New York under $4000",
    "Search for luxury properties in San Francisco",
    "List all available bookings"
  ];

  const handleQuickAction = (action: string) => {
    setInputValue(action);
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1>🏠 Real Estate Agent (A2A)</h1>
          <p>Powered by Amazon AgentCore</p>
          <div className="status-indicator">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span className="status-text">{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </header>

      {API_MODE === 'direct' && (
        <div className="token-warning">
          ⚠️ OAuth token expires in 60 minutes. If you get authentication errors, restart the UI with <code>./start-ui.sh</code>
        </div>
      )}

      <main className="app-main">
        <div className="chat-container">
          <div className="messages-container">
            {messages.map(message => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="loading-indicator">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="loading-text">Agent is thinking...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {messages.length === 1 && (
            <div className="quick-actions">
              <p className="quick-actions-title">Try asking:</p>
              <div className="quick-actions-grid">
                {quickActions.map((action, index) => (
                  <button
                    key={index}
                    className="quick-action-btn"
                    onClick={() => handleQuickAction(action)}
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="input-container">
            <textarea
              className="message-input"
              placeholder="Type your message here... (Press Enter to send)"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
              rows={1}
            />
            <button
              className="send-button"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
            >
              {isLoading ? '⏳' : '📤'}
            </button>
          </div>
        </div>
      </main>

      <footer className="app-footer">
        <p>Powered by AWS Bedrock AgentCore • A2A Protocol • OAuth 2.0</p>
      </footer>
    </div>
  );
}

export default App;
