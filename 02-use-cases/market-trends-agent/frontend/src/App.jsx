import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

// Sample broker profiles for quick demo setup
const SAMPLE_BROKERS = [
  {
    label: 'Growth Investor',
    card: `Name: Sarah Chen\nCompany: Morgan Stanley\nRole: Investment Advisor\nPreferred News Feed: Bloomberg\nIndustry Interests: technology, AI, cloud computing\nInvestment Strategy: growth investing\nRisk Tolerance: aggressive\nClient Demographics: younger professionals, tech workers\nGeographic Focus: North America, Asia-Pacific\nRecent Interests: artificial intelligence, semiconductor stocks`
  },
  {
    label: 'Conservative Advisor',
    card: `Name: James Mitchell\nCompany: Vanguard\nRole: Senior Portfolio Manager\nPreferred News Feed: Wall Street Journal\nIndustry Interests: utilities, healthcare, bonds\nInvestment Strategy: dividend investing\nRisk Tolerance: conservative\nClient Demographics: retirees, pension funds\nGeographic Focus: North America, Europe\nRecent Interests: treasury yields, defensive stocks`
  },
  {
    label: 'Emerging Markets',
    card: `Name: Maria Rodriguez\nCompany: JP Morgan Chase\nRole: Senior Investment Advisor\nPreferred News Feed: Reuters\nIndustry Interests: cryptocurrency, fintech, gaming\nInvestment Strategy: growth investing\nRisk Tolerance: aggressive\nClient Demographics: millennial retail investors\nGeographic Focus: Latin America, Asia-Pacific\nRecent Interests: blockchain technology, emerging market ETFs`
  }
]

// Suggested follow-up prompts to showcase agent capabilities
const SUGGESTED_PROMPTS = [
  { icon: '📊', text: 'Get me the current Apple stock price and analysis' },
  { icon: '📰', text: 'Search Bloomberg for latest AI sector news' },
  { icon: '🧠', text: 'What do you remember about my investment preferences?' },
  { icon: '📈', text: 'Give me a personalized market briefing for today' }
]

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [agentStatus, setAgentStatus] = useState('checking')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Generate session ID on mount and check agent health
  useEffect(() => {
    setSessionId(`demo-session-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`)
    checkAgentHealth()
  }, [])

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function checkAgentHealth() {
    try {
      const res = await fetch('/api/health')
      const data = await res.json()
      setAgentStatus(data.agent_deployed ? 'connected' : 'not_deployed')
    } catch {
      setAgentStatus('error')
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || loading) return
    const userMsg = { role: 'user', content: text, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId })
      })
      const data = await res.json()
      // Normalize escaped newlines — AgentCore may return literal \n instead of real line breaks
      let content = data.response || data.error || 'No response received'
      if (typeof content === 'string') {
        content = content.replace(/\\n/g, '\n').trim()
        // Strip wrapping quotes if the response was double-serialized
        if (content.startsWith('"') && content.endsWith('"')) {
          content = content.slice(1, -1).replace(/\\n/g, '\n').trim()
        }
      }
      const assistantMsg = {
        role: 'assistant',
        content,
        timestamp: new Date(),
        isError: !!data.error
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Connection error: ${err.message}. Is the backend running?`,
        timestamp: new Date(),
        isError: true
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function loadBrokerProfile(card) {
    setInput(card)
    setSidebarOpen(false)
    inputRef.current?.focus()
  }

  function resetSession() {
    setMessages([])
    setSessionId(`demo-session-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`)
  }

  const statusColors = { connected: '#22c55e', checking: '#eab308', not_deployed: '#ef4444', error: '#ef4444' }
  const statusLabels = { connected: 'Agent Connected', checking: 'Checking...', not_deployed: 'Agent Not Deployed', error: 'Backend Offline' }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar">
            ☰
          </button>
          <div className="logo">
            <span className="logo-icon">📈</span>
            <div>
              <h1>Market Trends Agent</h1>
              <span className="subtitle">Amazon Bedrock AgentCore Demo</span>
            </div>
          </div>
        </div>
        <div className="header-right">
          <div className="status" style={{ color: statusColors[agentStatus] }}>
            <span className="status-dot" style={{ background: statusColors[agentStatus] }} />
            {statusLabels[agentStatus]}
          </div>
          <button className="btn-reset" onClick={resetSession}>New Session</button>
        </div>
      </header>

      <div className="main">
        {/* Sidebar — Broker Profiles & Feature Highlights */}
        {sidebarOpen && (
          <aside className="sidebar">
            <section className="sidebar-section">
              <h3>Quick Demo Profiles</h3>
              <p className="sidebar-hint">Load a broker profile to start a personalized demo</p>
              {SAMPLE_BROKERS.map((b, i) => (
                <button key={i} className="broker-btn" onClick={() => loadBrokerProfile(b.card)}>
                  {b.label}
                </button>
              ))}
            </section>

            <section className="sidebar-section">
              <h3>AgentCore Features</h3>
              <div className="feature-list">
                <div className="feature"><span>🧠</span> Multi-Strategy Memory</div>
                <div className="feature"><span>🌐</span> Browser Automation</div>
                <div className="feature"><span>📊</span> Live Stock Data</div>
                <div className="feature"><span>📰</span> Multi-Source News</div>
                <div className="feature"><span>🤖</span> LangGraph Agent</div>
                <div className="feature"><span>🔐</span> Broker Identity (LLM)</div>
              </div>
            </section>

            <section className="sidebar-section">
              <h3>Session</h3>
              <code className="session-id">{sessionId.slice(0, 24)}...</code>
            </section>
          </aside>
        )}

        {/* Chat Area */}
        <div className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">📈</div>
              <h2>Market Trends Agent</h2>
              <p>Personalized financial intelligence powered by Amazon Bedrock AgentCore</p>
              <div className="welcome-grid">
                {SUGGESTED_PROMPTS.map((p, i) => (
                  <button key={i} className="suggestion-btn" onClick={() => sendMessage(p.text)}>
                    <span className="suggestion-icon">{p.icon}</span>
                    {p.text}
                  </button>
                ))}
              </div>
              <p className="welcome-hint">Or load a broker profile from the sidebar to start a personalized demo →</p>
            </div>
          ) : (
            <div className="messages">
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
                  <div className="message-avatar">{msg.role === 'user' ? '👤' : '📈'}</div>
                  <div className="message-content">
                    <div className="message-role">{msg.role === 'user' ? 'You' : 'Market Trends Agent'}</div>
                    {msg.role === 'assistant' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    ) : (
                      <pre className="user-pre">{msg.content}</pre>
                    )}
                    <span className="message-time">{msg.timestamp.toLocaleTimeString()}</span>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="message assistant">
                  <div className="message-avatar">📈</div>
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span /><span /><span />
                    </div>
                    <span className="thinking-text">Analyzing markets...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Suggested follow-ups after first exchange */}
          {messages.length > 0 && !loading && (
            <div className="follow-ups">
              {SUGGESTED_PROMPTS.map((p, i) => (
                <button key={i} className="follow-up-btn" onClick={() => sendMessage(p.text)}>
                  {p.icon} {p.text}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <form className="input-bar" onSubmit={e => { e.preventDefault(); sendMessage(input) }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
              placeholder="Ask about markets, stocks, or paste a broker profile..."
              rows={input.split('\n').length > 3 ? 6 : 2}
              disabled={loading}
              aria-label="Chat message input"
            />
            <button type="submit" disabled={loading || !input.trim()} aria-label="Send message">
              {loading ? '⏳' : '➤'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
