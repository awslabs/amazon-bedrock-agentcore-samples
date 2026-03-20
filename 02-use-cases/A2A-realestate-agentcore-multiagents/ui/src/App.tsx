import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import ChatMessage from './components/ChatMessage';
import { sendMessage, checkHealth } from './services/api';
import * as directApi from './services/directApi';

const API_MODE = import.meta.env.VITE_API_MODE || 'proxy';
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
    api.checkHealth()
      .then(() => setIsConnected(true))
      .catch(() => setIsConnected(false));

    setMessages([{
      id: '1',
      text: "Hello! I'm your Real Estate Agent (A2A) powered by Amazon Bedrock AgentCore. I can help you search for properties and make bookings. What are you looking for today?",
      sender: 'agent',
      timestamp: new Date()
    }]);
  }, []);

  useEffect(() => {
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
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: response.response,
        sender: 'agent',
        timestamp: new Date()
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        sender: 'agent',
        timestamp: new Date()
      }]);
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
    "Show me 2-bedroom houses in Seattle",
    "Search for luxury properties in San Francisco",
    "List all available bookings"
  ];

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <div className="header-left">
            <div className="header-logo">
              <span>A2A</span>
              REAL ESTATE AGENT
            </div>
            <div className="header-divider"></div>
            <div className="header-nav">
              <span className="header-nav-item active">⬡ Chat</span>
            </div>
          </div>
          <div className="status-indicator">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span className="status-text">{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <div className="chat-container">
          <div className="messages-container">
            {messages.map(message => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="loading-indicator">
                <div className="typing-dots">
                  <span></span><span></span><span></span>
                </div>
                <span className="loading-text">Thinking...</span>
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
                    onClick={() => setInputValue(action)}
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
              placeholder="Type your message... (Press Enter to send)"
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
              aria-label="Send message"
            >
              {isLoading ? '...' : '→'}
            </button>
          </div>
        </div>
      </main>

      <footer className="app-footer">
        <p>Powered by Amazon Bedrock AgentCore</p>
      </footer>
    </div>
  );
}

export default App;
