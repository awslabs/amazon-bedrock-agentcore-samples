import { useState, useEffect, useRef, useMemo } from 'react'
import { invokeAgentCore, type ChatMessage, type SubagentStep } from '../services/awsCalls'
import { type Session, createSession, saveMessage } from '../services/bedrockSessionService'
import { submitFeedback } from '../services/feedbackService'
import { userProfileService } from '../services/userProfileService'
import { getCartItems, removeCartItems, type CartItem } from '../services/cartService'
import { createBooking } from '../services/bookingsService'
import { showToast } from '../utils/toast'
import { matchesAnyKeywordGroup, BUTTON_KEYWORDS } from '../utils/keywordMatcher'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import CardOnboarding from './CardOnboarding'
import PurchaseConfirmation from './PurchaseConfirmation'
import { VisaIframe } from './VisaIframe'

// Component for rendering thinking content
const ThinkingSection = ({ thinkingContent }: { thinkingContent: string }) => {
  // Clean up the thinking content by removing extra spaces and newlines
  const cleanContent = thinkingContent
    .replace(/<thinking>/g, '') // Remove opening tag
    .replace(/<\/thinking>/g, '') // Remove closing tag
    .trim() // Remove leading/trailing whitespace
    .replace(/\n\s*\n/g, '\n') // Replace multiple newlines with single newline
    .replace(/^\s+/gm, '') // Remove leading spaces from each line
    .replace(/\s+$/gm, '') // Remove trailing spaces from each line

  return (
    <div className="thinking-section">
      <details className="thinking-details">
        <summary className="thinking-summary">💭 Thinking...</summary>
        <div className="thinking-content">
          <div className="thinking-text">
            {cleanContent.split('\n').filter(line => line.trim()).map((line, index) => (
              <p key={index} className="thinking-paragraph">
                {line}
              </p>
            ))}
          </div>
        </div>
      </details>
    </div>
  )
}


// Component for rendering previous loops and subagent steps
const PreviousLoopsSection = ({ 
  previousLoops, 
  subagentSteps,
  currentSubagent
}: { 
  previousLoops?: string[];
  subagentSteps?: SubagentStep[];
  currentSubagent?: {
    name: string;
    input: string;
    tool?: string;
    content?: string;
  };
}) => {
  const hasLoops = previousLoops && previousLoops.length > 0;
  const hasSubagentSteps = subagentSteps && subagentSteps.length > 0;
  const hasCurrentSubagent = currentSubagent && currentSubagent.content;
  
  if (!hasLoops && !hasSubagentSteps && !hasCurrentSubagent) return null;

  const totalSteps = (previousLoops?.length || 0) + (subagentSteps?.length || 0) + (hasCurrentSubagent ? 1 : 0);

  return (
    <div className="previous-loops-section">
      <details className="previous-loops-details">
        <summary className="previous-loops-summary">
          🔄 Previous processing steps ({totalSteps})
        </summary>
        <div className="previous-loops-content">
          {/* Render previous loops */}
          {previousLoops?.map((loopContent, index) => (
            <div key={`loop-${index}`} className="previous-loop-item">
              <div className="previous-loop-header">Processing Step {index + 1}</div>
              <div className="previous-loop-content">
                <MarkdownRenderer content={loopContent} isAssistant={true} />
              </div>
            </div>
          ))}
          
          {/* Render completed subagent steps */}
          {subagentSteps?.map((step, index) => {
            return (
              <div key={`subagent-${index}`} className="previous-loop-item subagent-step">
                <div className="previous-loop-header">
                  🤖 {step.agentName}
                </div>
                <div className="subagent-input">
                  <strong>Input:</strong> {step.input}
                </div>
                <div className="previous-loop-content">
                  <MarkdownRenderer content={step.content} isAssistant={true} />
                </div>
              </div>
            );
          })}
          
          {/* Render current streaming subagent */}
          {currentSubagent && currentSubagent.content && (
            <div className="previous-loop-item subagent-step current-subagent">
              <div className="previous-loop-header">
                🤖 {currentSubagent.name} (streaming...)
              </div>
              <div className="subagent-input">
                <strong>Input:</strong> {currentSubagent.input}
              </div>
              <div className="previous-loop-content">
                <MarkdownRenderer content={currentSubagent.content} isAssistant={true} />
                <span className="streaming-cursor">|</span>
              </div>
            </div>
          )}
        </div>
      </details>
    </div>
  )
}

// Enhanced markdown renderer component
const MarkdownRenderer = ({ content, isAssistant = false }: { content: string; isAssistant?: boolean }) => {
  if (!content) return null

  // Clean up content for better rendering
  const processedContent = isAssistant ? content.trim() : content

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // Custom heading renderer
          h1: ({ children }) => <h1 className="markdown-h1">{children}</h1>,
          h2: ({ children }) => <h2 className="markdown-h2">{children}</h2>,
          h3: ({ children }) => <h3 className="markdown-h3">{children}</h3>,
          h4: ({ children }) => <h4 className="markdown-h4">{children}</h4>,
          h5: ({ children }) => <h5 className="markdown-h5">{children}</h5>,
          h6: ({ children }) => <h6 className="markdown-h6">{children}</h6>,
          
          // Custom paragraph renderer
          p: ({ children }) => <p className="markdown-p">{children}</p>,
          
          // Custom list renderers
          ul: ({ children }) => <ul className="markdown-ul">{children}</ul>,
          ol: ({ children }) => <ol className="markdown-ol">{children}</ol>,
          li: ({ children }) => <li className="markdown-li">{children}</li>,
          
          // Custom code renderers
          code: ({ className, children, ...props }: any) => {
            const match = /language-(\w+)/.exec(className || '')
            const isInline = !match
            return isInline ? (
              <code className="markdown-inline-code" {...props}>
                {children}
              </code>
            ) : (
              <pre className="markdown-pre">
                <code className={`markdown-code ${className}`} {...props}>
                  {children}
                </code>
              </pre>
            )
          },
          
          // Custom blockquote renderer
          blockquote: ({ children }) => <blockquote className="markdown-blockquote">{children}</blockquote>,
          
          // Custom table renderers
          table: ({ children }) => <table className="markdown-table">{children}</table>,
          thead: ({ children }) => <thead className="markdown-thead">{children}</thead>,
          tbody: ({ children }) => <tbody className="markdown-tbody">{children}</tbody>,
          tr: ({ children }) => <tr className="markdown-tr">{children}</tr>,
          th: ({ children }) => <th className="markdown-th">{children}</th>,
          td: ({ children }) => <td className="markdown-td">{children}</td>,
          
          // Custom link renderer
          a: ({ href, children }) => (
            <a 
              href={href} 
              className="markdown-link" 
              target="_blank" 
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          
          // Custom emphasis renderers
          strong: ({ children }) => <strong className="markdown-strong">{children}</strong>,
          em: ({ children }) => <em className="markdown-em">{children}</em>,
          
          // Custom horizontal rule
          hr: () => <hr className="markdown-hr" />,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  )
}

interface User {
  username: string
  email?: string
  userId: string
  name?: string
}

interface ChatProps {
  user: User
  onSignOut: () => void
  currentSession: Session | null
  sessions?: Session[]
  onSwitchSession?: (sessionId: string) => void
  getMessages: (sessionId: string) => Promise<ChatMessage[]>
  refreshSessions?: () => Promise<void>
  updateCurrentSession?: (session: Session) => void
  onMessagesUpdate?: (messages: ChatMessage[]) => void
  triggerMessage?: { message: string; timestamp: number }
  onNewChat?: () => void
  canStartNewChat?: boolean
  onCartUpdate?: () => void
}

const Chat = ({ user, currentSession, sessions = [], onSwitchSession, getMessages, refreshSessions, updateCurrentSession, onMessagesUpdate, onNewChat, canStartNewChat = true, onCartUpdate }: ChatProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [copiedMessageId, setCopiedMessageId] = useState<string>('')
  const [showCommentBox, setShowCommentBox] = useState<string>('')
  const [feedbackComment, setFeedbackComment] = useState('')
  const [feedbackType, setFeedbackType] = useState<'up' | 'down' | null>(null)
  const [submittingFeedback, setSubmittingFeedback] = useState<string>('')
  const [messageFeedback, setMessageFeedback] = useState<Record<string, { feedback: 'up' | 'down', comment?: string }>>({})
  const [showCardForm, setShowCardForm] = useState(false)
  const [showPurchaseConfirmation, setShowPurchaseConfirmation] = useState(false)
  const [purchaseCartItems, setPurchaseCartItems] = useState<CartItem[]>([])
  const [visaIframeConfig, setVisaIframeConfig] = useState<any>(null)
  const [showSessionDropdown, setShowSessionDropdown] = useState(false)
  const [cardCheckResults, setCardCheckResults] = useState<Record<string, boolean>>({})
  const [hasCartItems, setHasCartItems] = useState(false)
  const [userExpressedPurchaseIntent, setUserExpressedPurchaseIntent] = useState(false)
  const [purchaseIntentMessageIndex, setPurchaseIntentMessageIndex] = useState<number>(-1)
  const [lastPurchaseTime, setLastPurchaseTime] = useState<number>(0)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const sessionDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sessionDropdownRef.current && !sessionDropdownRef.current.contains(event.target as Node)) {
        setShowSessionDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Notify parent when messages change
  useEffect(() => {
    if (onMessagesUpdate) {
      onMessagesUpdate(messages)
    }
  }, [messages, onMessagesUpdate])

  // Check card status for messages that need it (CONFIRM_PURCHASE keywords)
  useEffect(() => {
    const checkCardStatus = async () => {
      for (const message of messages) {
        if (message.role === 'assistant' && !message.isStreaming) {
          // Check if message has CONFIRM_PURCHASE keywords
          const hasPurchaseKeywords = matchesAnyKeywordGroup(message.content, BUTTON_KEYWORDS.CONFIRM_PURCHASE) ||
            (message.currentLoop && matchesAnyKeywordGroup(message.currentLoop, BUTTON_KEYWORDS.CONFIRM_PURCHASE))

          // Only check if we don't have a result yet and keywords match
          if (hasPurchaseKeywords && cardCheckResults[message.id] === undefined) {
            console.log(`[CARD CHECK] Message ${message.id}: Checking card status for user ${user.userId}`)
            try {
              const enrolledCard = await userProfileService.getEnrolledCard(user.userId)
              console.log(`[CARD CHECK] Message ${message.id}: enrolledCard result:`, enrolledCard)
              const hasCard = !!enrolledCard
              console.log(`[CARD CHECK] Message ${message.id}: Setting hasCard = ${hasCard}`)
              setCardCheckResults(prev => ({
                ...prev,
                [message.id]: hasCard
              }))
            } catch (error) {
              console.error(`[CARD CHECK] Message ${message.id}: Error checking card status:`, error)
              setCardCheckResults(prev => ({
                ...prev,
                [message.id]: false
              }))
            }
          }
        }
      }
    }

    checkCardStatus()
  }, [messages, user.userId, cardCheckResults])

  // Check if cart has items when messages with purchase keywords appear
  useEffect(() => {
    const checkCartItems = async () => {
      try {
        const items = await getCartItems(user.userId)
        setHasCartItems(items && items.length > 0)
      } catch (error) {
        console.error('Error checking cart items:', error)
        setHasCartItems(false)
      }
    }

    // Check cart whenever messages change (especially after purchase)
    const lastMessage = messages[messages.length - 1]
    if (lastMessage && lastMessage.role === 'assistant') {
      const hasPurchaseKeywords = matchesAnyKeywordGroup(lastMessage.content, BUTTON_KEYWORDS.CONFIRM_PURCHASE) ||
        (lastMessage.currentLoop && matchesAnyKeywordGroup(lastMessage.currentLoop, BUTTON_KEYWORDS.CONFIRM_PURCHASE))

      if (hasPurchaseKeywords) {
        checkCartItems()
      }
    }
  }, [messages, user.userId])

  // Detect user purchase intent from their messages
  useEffect(() => {
    // Look at recent user messages (last 3) to detect purchase intent
    const recentUserMessages = messages
      .filter(m => m.role === 'user')
      .slice(-3)

    const hasRecentPurchaseIntent = recentUserMessages.some(msg =>
      matchesAnyKeywordGroup(msg.content, BUTTON_KEYWORDS.USER_PURCHASE_INTENT)
    )

    // Reset purchase intent if purchase was completed recently (within 30 seconds)
    const timeSinceLastPurchase = Date.now() - lastPurchaseTime
    if (timeSinceLastPurchase < 30000) {
      setUserExpressedPurchaseIntent(false)
      setPurchaseIntentMessageIndex(-1)
    } else {
      setUserExpressedPurchaseIntent(hasRecentPurchaseIntent)

      // Track the index of the message where user expressed purchase intent
      if (hasRecentPurchaseIntent) {
        const intentMessage = recentUserMessages.find(msg =>
          matchesAnyKeywordGroup(msg.content, BUTTON_KEYWORDS.USER_PURCHASE_INTENT)
        )
        if (intentMessage) {
          const intentIndex = messages.findIndex(m => m.id === intentMessage.id)
          setPurchaseIntentMessageIndex(intentIndex)
        }
      } else {
        setPurchaseIntentMessageIndex(-1)
      }
    }
  }, [messages, lastPurchaseTime])

  // Helper function to extract thinking content from message
  const extractThinkingContent = (content: string): { mainContent: string; thinkingContent?: string } => {
    const thinkingRegex = /<thinking>([\s\S]*?)<\/thinking>/g
    const matches = content.match(thinkingRegex)
    
    if (matches && matches.length > 0) {
      // Extract all thinking blocks
      const thinkingContent = matches.join('\n')
      // Remove thinking blocks from main content
      const mainContent = content.replace(thinkingRegex, '').trim()
      
      return {
        mainContent,
        thinkingContent
      }
    }
    
    return { mainContent: content }
  }

  // Load messages when switching sessions
  useEffect(() => {
    const loadMessages = async () => {
      if (currentSession && !currentSession.isTemporary) {
        // Load messages for existing (permanent) sessions
        try {
          const sessionMessages = await getMessages(currentSession.id)
          
          // Convert Bedrock messages to Chat messages
          const convertedMessages: ChatMessage[] = sessionMessages.map(msg => {
            
            // Extract thinking content for assistant messages
            if (msg.role === 'assistant') {
              const { mainContent, thinkingContent } = extractThinkingContent(msg.content)
              return {
                id: msg.id,
                role: msg.role as 'user' | 'assistant',
                content: mainContent,
                thinkingContent: thinkingContent
              }
            }
            
            return {
              id: msg.id,
              role: msg.role as 'user' | 'assistant',
              content: msg.content,
            }
          })
          
          setMessages(convertedMessages)
          console.log(`Loaded ${convertedMessages.length} messages from session ${currentSession.id}`)
          
        } catch (error) {
          console.error('Error loading session messages:', error)
          setMessages([])
        }
      } else if (!currentSession || currentSession.isTemporary) {
        // Clear messages for new conversations (no session or temporary session)
        setMessages([])
        console.log('Cleared messages for new conversation')
      }
    }
    
    loadMessages()
  }, [currentSession?.id, currentSession?.isTemporary, getMessages])

  // Auto-resize textarea based on content
  const autoResizeTextarea = (textarea: HTMLTextAreaElement) => {
    textarea.style.height = 'auto'
    const lineHeight = 24 // Approximate line height in pixels
    const maxLines = 7
    const maxHeight = lineHeight * maxLines
    
    if (textarea.scrollHeight <= maxHeight) {
      textarea.style.height = `${textarea.scrollHeight}px`
      textarea.style.overflowY = 'hidden'
    } else {
      textarea.style.height = `${maxHeight}px`
      textarea.style.overflowY = 'auto'
    }
  }

  // Helper function to copy message content
  const copyToClipboard = async (content: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedMessageId(messageId)
      setTimeout(() => setCopiedMessageId(''), 2000) // Clear after 2 seconds
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

  // Enhanced feedback handlers with visual state management
  const handleFeedback = async (messageId: string, feedback: 'up' | 'down') => {
    if (submittingFeedback === messageId) return // Prevent double submission
    
    setSubmittingFeedback(messageId)
    try {
      await submitFeedback(messageId, feedback, user.userId)
      console.log(`✅ Feedback submitted: ${feedback} for message ${messageId}`)
      
      // Update local feedback state to show visual indicator
      setMessageFeedback(prev => ({
        ...prev,
        [messageId]: { feedback }
      }))
      
    } catch (error) {
      console.error('❌ Error submitting feedback:', error)
    } finally {
      setSubmittingFeedback('')
    }
  }

  // Reserved for future use: allow users to provide comments with feedback
  // const handleFeedbackWithComment = (messageId: string, feedback: 'up' | 'down') => {
  //   setShowCommentBox(messageId)
  //   setFeedbackType(feedback) // Store the feedback type
  //   setFeedbackComment('')
  // }

  const cancelFeedback = () => {
    setShowCommentBox('')
    setFeedbackComment('')
    setFeedbackType(null)
  }

  const submitFeedbackWithComment = async () => {
    const messageId = showCommentBox
    if (!messageId || !feedbackType) return

    if (submittingFeedback === messageId) return // Prevent double submission

    setSubmittingFeedback(messageId)
    try {
      await submitFeedback(messageId, feedbackType, user.userId, feedbackComment)
      console.log('✅ Feedback with comment submitted successfully')

      // Update local feedback state to show visual indicator
      setMessageFeedback(prev => ({
        ...prev,
        [messageId]: { feedback: feedbackType, comment: feedbackComment }
      }))

      setShowCommentBox('')
      setFeedbackComment('')
      setFeedbackType(null)
    } catch (error) {
      console.error('❌ Error submitting feedback with comment:', error)
    } finally {
      setSubmittingFeedback('')
    }
  }

  // Purchase confirmation handlers
  const handleOpenPurchaseConfirmation = async () => {
    try {
      // Fetch cart items
      const items = await getCartItems(user.userId)
      if (!items || items.length === 0) {
        showToast.warning('Your cart is empty. Please add items before purchasing.')
        return
      }

      setPurchaseCartItems(items)
      setShowPurchaseConfirmation(true)
    } catch (error) {
      console.error('Error loading cart for purchase:', error)
      showToast.error('Failed to load cart items. Please try again.')
    }
  }

  const handlePurchaseComplete = async (result: any) => {
    setShowPurchaseConfirmation(false)
    setPurchaseCartItems([])

    // Clear card check cache to force re-check for future purchases
    setCardCheckResults({})

    // Mark cart as empty after purchase
    setHasCartItems(false)

    // Reset purchase intent and record purchase time
    setUserExpressedPurchaseIntent(false)
    setLastPurchaseTime(Date.now())

    console.log('✅ Purchase complete in Chat component')

    // Generate order ID
    const orderId = `ORD-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${result.instructionId?.slice(-8) || 'XXXX'}`

    // Remove purchased items from cart
    try {
      const asins: string[] = result.cartItems
        .filter((item: any) => item.asin)
        .map((item: any) => item.asin)

      console.log('🛒 Removing purchased items from cart:', asins)
      await removeCartItems(user.userId, asins)
      console.log('🛒 Purchased items removed from cart')
    } catch (error) {
      console.error('Error removing purchased items from cart:', error)
    }

    // Create booking records for purchase history
    try {
      console.log('📋 Creating booking records for purchased items...')
      for (const item of result.cartItems) {
        await createBooking(user.userId, orderId, {
          title: item.title,
          price: item.price,
          asin: item.asin,
          url: item.url
        })
      }
      console.log('📋 Booking records created successfully')
    } catch (error) {
      console.error('Error creating booking records:', error)
    }

    // Refresh cart count
    if (onCartUpdate) {
      onCartUpdate()
    }

    // Send purchase confirmation to agent so it can acknowledge
    const purchaseSummary = `Purchase completed successfully! ${result.cartItems?.length || 0} items purchased for $${result.totalAmount}. Order ID: ${orderId}`

    // DO NOT add system message to UI - send directly to agent without showing in chat
    setLoading(true)

    try {
      let actualSessionId = currentSession?.id

      // Use existing session
      if (actualSessionId) {
        // Save system message to database (for agent context) but don't add to UI
        await saveMessage(actualSessionId, 'user', purchaseSummary)

        // Send to agent - agent's response will appear in UI
        const setAnswers = (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
          setMessages(currentMessages => {
            const newMessages = updater(currentMessages)
            const lastMessage = newMessages[newMessages.length - 1]
            if (lastMessage &&
                lastMessage.role === 'assistant' &&
                !lastMessage.isStreaming &&
                lastMessage.status === 'complete' &&
                actualSessionId) {
              saveMessage(actualSessionId, 'assistant', lastMessage.content)
                .then(() => console.log('Saved purchase acknowledgment to AppSync'))
                .catch(error => console.error('Error saving acknowledgment:', error))
            }
            return newMessages
          })
        }

        await invokeAgentCore(
          purchaseSummary,
          user.userId,
          actualSessionId,
          setAnswers,
        )
      }
    } catch (error) {
      console.error('Error notifying agent of purchase:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePurchaseError = (error: string) => {
    setShowPurchaseConfirmation(false)
    setPurchaseCartItems([])
    // Show error toast for UI/system errors (not agent errors)
    showToast.error(`Purchase failed: ${error}. Please try again.`)
  }

  const handlePurchaseCancel = () => {
    setShowPurchaseConfirmation(false)
    setPurchaseCartItems([])
    // No toast needed - user just closed the modal
  }

  // Helper function to get status display text and icon
  const getStatusDisplay = (status?: string) => {
    if (!status) return null
    
    // Handle descriptive status strings
    if (status.toLowerCase().includes('preparing')) {
      return { text: status, icon: '🔄', className: 'status-preparing' }
    } else if (status.toLowerCase().includes('using tool') || status.toLowerCase().includes('using ')) {
      return { text: status, icon: '🔧', className: 'status-using-tool' }
    } else if (status.toLowerCase().includes('calling ')) {
      return { text: status, icon: '🤖', className: 'status-calling-subagent' }
    } else if (status.toLowerCase().includes('thinking')) {
      return { text: status, icon: '🧠', className: 'status-thinking' }
    } else if (status.toLowerCase() === 'complete') {
      return { text: status, icon: '✅', className: 'status-complete' }
    } else if (status.toLowerCase().includes('processing')) {
      return { text: status, icon: '⚙️', className: 'status-processing' }
    } else {
      // Default for any other status
      return { text: status, icon: '⚙️', className: 'status-default' }
    }
  }

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(e)
    }
  }

  // Programmatically send a message (used by quick action buttons)
  const handleSendMessage = (message: string) => {
    setInputMessage(message)
    // Trigger send after state update
    setTimeout(() => {
      const form = document.querySelector('.chat-input-form') as HTMLFormElement
      if (form) {
        form.requestSubmit()
      }
    }, 0)
  }

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!inputMessage.trim() || loading) return

    const messageText = inputMessage.trim()
    setInputMessage('')
    
    // Reset textarea height after clearing message
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.overflowY = 'hidden'
    }

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
    }

    // Add user message to conversation history (maintain conversation)
    setMessages(prev => [...prev, userMessage])
    setLoading(true)

    let actualSessionId = currentSession?.id
    let isNewSession = false
    let assistantMessageSaved = false // Flag to prevent duplicate saves

    try {
      // Create new session ONLY if there's no current session at all
      if (!currentSession) {
        console.log('No current session found, creating new session...')
        // Use first 100 characters of user message as session title
        const sessionTitle = messageText.length > 100 
          ? messageText.substring(0, 100).trim() + '...'
          : messageText.trim()
        const newSession = await createSession(user.userId, sessionTitle)
        actualSessionId = newSession.id
        isNewSession = true
        console.log('Created new session:', actualSessionId)
        
        // Update the current session state immediately
        if (updateCurrentSession) {
          updateCurrentSession(newSession)
        }
      } else if (currentSession.isTemporary) {
        // If we have a temporary session, create a permanent one and use its ID
        console.log('Converting temporary session to permanent...')
        const sessionTitle = messageText.length > 100 
          ? messageText.substring(0, 100).trim() + '...'
          : messageText.trim()
        const newSession = await createSession(user.userId, sessionTitle)
        actualSessionId = newSession.id
        isNewSession = true
        console.log('Created permanent session:', actualSessionId)
        
        // Update the current session state immediately
        if (updateCurrentSession) {
          updateCurrentSession(newSession)
        }
      } else {
        // Use existing session
        actualSessionId = currentSession.id
        console.log('Using existing session:', actualSessionId)
      }

      // Save user message to AppSync
      if (actualSessionId) {
        try {
          await saveMessage(actualSessionId, 'user', messageText)
          console.log('Saved user message to AppSync')
        } catch (error) {
          console.error('Error saving user message:', error)
        }
      }

      // Enhanced function to update streaming response and handle completion
      const setAnswers = (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
        setMessages(currentMessages => {
          const newMessages = updater(currentMessages)
          
          // Check if any assistant message just completed and hasn't been saved yet
          const lastMessage = newMessages[newMessages.length - 1]
          if (lastMessage && 
              lastMessage.role === 'assistant' && 
              !lastMessage.isStreaming && 
              lastMessage.status === 'complete' &&
              actualSessionId &&
              !assistantMessageSaved) {
            
            // Mark as saved to prevent duplicates
            assistantMessageSaved = true
            
            // Save the completed assistant message to AppSync
            saveMessage(actualSessionId, 'assistant', lastMessage.content)
              .then(() => console.log('Saved completed assistant message to AppSync'))
              .catch(error => console.error('Error saving completed assistant message:', error))
          }
          
          return newMessages
        })
      }

      // Call Agent Core with session ID
      console.log('Sending message with session ID:', actualSessionId)
      await invokeAgentCore(
        messageText,
        user.userId, // User ID
        actualSessionId || `session-${user.userId}-${Date.now()}`, // Use session ID
        setAnswers,
      )

      // Assistant message will be saved automatically when AgentCore completes
      // via the enhanced setAnswers callback above
      console.log('Assistant message will be saved when AgentCore signals completion')

      // If this was a new session, refresh sessions
      if (isNewSession && refreshSessions) {
        console.log('Refreshing sessions after creating new session...')
        // Refresh sessions with retry logic to ensure backend has processed the new session
        const refreshWithRetry = async (retries = 3, delay = 1000) => {
          for (let i = 0; i < retries; i++) {
            await new Promise(resolve => setTimeout(resolve, delay))
            try {
              await refreshSessions()
              console.log(`Session refresh attempt ${i + 1} completed`)
              break
            } catch (error) {
              console.error(`Session refresh attempt ${i + 1} failed:`, error) // nosemgrep
              if (i === retries - 1) {
                console.error('All session refresh attempts failed')
              }
            }
          }
        }
        refreshWithRetry()
      }

    } catch (error) {
      console.error('Error sending message:', error)
      
      // Add error message
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your message. Please try again.',
      }
      
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
      // Assistant message saving is now handled in the setAnswers callback
      // when AgentCore signals completion - no duplicate saving needed here
    }
  }

  // Check if there are any assistant messages (for enabling New Chat button)
  const hasAssistantMessages = messages.some(m => m.role === 'assistant' && !m.isStreaming)

  // Memoize the last assistant message ID to prevent infinite re-renders
  const lastAssistantMessageId = useMemo(() => {
    const assistantMessages = messages.filter(m => m.role === 'assistant' && !m.isStreaming)
    return assistantMessages.length > 0 ? assistantMessages[assistantMessages.length - 1].id : null
  }, [messages])

  return (
    <div className="w-1/2 flex flex-col bg-white m-3 rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-[#f0f4ff]">
        <div className="relative" ref={sessionDropdownRef}>
          <button
            onClick={() => sessions.length > 0 && setShowSessionDropdown(!showSessionDropdown)}
            className={`flex items-center gap-1.5 font-medium text-gray-700 ${sessions.length > 0 ? 'hover:text-[#1668e3] cursor-pointer' : ''}`}
          >
            <span>Recent Sessions ({sessions.length})</span>
            {sessions.length > 0 && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: showSessionDropdown ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
                <path d="M6 9l6 6 6-6"/>
              </svg>
            )}
          </button>
          {showSessionDropdown && sessions.length > 0 && (
            <div className="absolute top-full left-0 mt-1 w-72 max-h-80 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg z-50">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => {
                    onSwitchSession?.(session.id)
                    setShowSessionDropdown(false)
                  }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-b-0 ${
                    currentSession?.id === session.id ? 'bg-[#f0f4ff] text-[#1668e3]' : 'text-gray-700'
                  }`}
                >
                  <div className="truncate font-medium">{session.title || 'Untitled'}</div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {new Date(session.createdAt).toLocaleDateString()}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        {onNewChat && (
          <button 
            onClick={onNewChat}
            disabled={!canStartNewChat || !hasAssistantMessages}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-[#1668e3] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            New Session
          </button>
        )}
      </div>
      <div className="flex-1 flex flex-col overflow-hidden">
        <div 
          className="flex-1 overflow-y-auto p-4 flex flex-col gap-4" 
          ref={messagesContainerRef}
        >
          {messages.length === 0 && (
            <div className="text-center text-gray-500 italic py-8 px-4 bg-gray-50 rounded-lg mx-auto max-w-md">
              Hi {user.name || user.username}! I'm your AI assistant. Ask me anything!
            </div>
          )}
          
          {messages.map((message) => {
            const statusDisplay = message.role === 'assistant' ? getStatusDisplay(message.status) : null
            const currentFeedback = messageFeedback[message.id]
            
            return (
              <div key={message.id} className={`message-wrapper ${message.role}`}>
                {/* Status Row Above Message Box for Assistant Messages */}
                {statusDisplay && statusDisplay.className !== 'status-complete' && (
                  <div className={`message-status-row ${statusDisplay.className}`}>
                    <span className="status-icon">{statusDisplay.icon}</span>
                    <span className="status-text">{statusDisplay.text}</span>
                  </div>
                )}
                
                <div className={`message ${message.role}`}>
                  <div className="message-content">
                    {/* Render thinking section if present */}
                    {message.role === 'assistant' && message.thinkingContent && (
                      <ThinkingSection thinkingContent={message.thinkingContent} />
                    )}
                    
                    {/* Render previous loops and subagent steps section if present */}
                    {message.role === 'assistant' && ((message.previousLoops && message.previousLoops.length > 0) || (message.subagentSteps && message.subagentSteps.length > 0) || (message.currentSubagent && message.currentSubagent.content)) && (
                      <PreviousLoopsSection 
                        previousLoops={message.previousLoops} 
                        subagentSteps={message.subagentSteps}
                        currentSubagent={message.currentSubagent}
                      />
                    )}
                    
                    <div className="formatted-message">
                      <MarkdownRenderer 
                        content={message.currentLoop || message.content} 
                        isAssistant={message.role === 'assistant'} 
                      />
                      {message.isStreaming && (
                        <span className="streaming-cursor">|</span>
                      )}
                    </div>
                    
                    {/* Button Rendering Logic with Mutual Exclusion
                        Priority: CONFIRM_PURCHASE (if has card) > ADD_CARD (if no card OR check pending)
                        NEVER show both buttons at once
                        Only show buttons on the LAST assistant message */}
                    {(() => {
                      // Skip if not an assistant message or still streaming
                      if (message.role !== 'assistant' || message.isStreaming) return null

                      // Only show buttons on the last assistant message (using memoized value)
                      if (!lastAssistantMessageId || message.id !== lastAssistantMessageId) {
                        return null
                      }

                      // IMPORTANT: Only show buttons on messages that come AFTER user expressed purchase intent
                      // This prevents buttons from appearing on older messages before the user said "buy" / "checkout"
                      const currentMessageIndex = messages.findIndex(m => m.id === message.id)
                      if (purchaseIntentMessageIndex >= 0 && currentMessageIndex <= purchaseIntentMessageIndex) {
                        return null
                      }

                      // Check for keyword matches
                      const hasAddCardKeywords = matchesAnyKeywordGroup(message.content, BUTTON_KEYWORDS.ADD_CARD) ||
                        (message.currentLoop && matchesAnyKeywordGroup(message.currentLoop, BUTTON_KEYWORDS.ADD_CARD))

                      const hasPurchaseKeywords = matchesAnyKeywordGroup(message.content, BUTTON_KEYWORDS.CONFIRM_PURCHASE) ||
                        (message.currentLoop && matchesAnyKeywordGroup(message.currentLoop, BUTTON_KEYWORDS.CONFIRM_PURCHASE))

                      // Get card check result (undefined means check in progress or not started)
                      const hasCard = cardCheckResults[message.id]

                      // Debug logging
                      if (hasAddCardKeywords || hasPurchaseKeywords) {
                        console.log(`[BUTTON LOGIC] Message ${message.id}:`, {
                          hasAddCardKeywords,
                          hasPurchaseKeywords,
                          hasCard,
                          hasCartItems,
                          userExpressedPurchaseIntent,
                          cardCheckResults: cardCheckResults[message.id],
                          isLastAssistantMessage: true
                        })
                      }

                      // PRIORITY 1: CONFIRM_PURCHASE button
                      // ONLY show if: user expressed purchase intent AND agent confirms AND card exists AND cart has items
                      if (userExpressedPurchaseIntent && hasPurchaseKeywords && hasCard === true && hasCartItems) {
                        console.log(`[BUTTON LOGIC] Message ${message.id}: Showing CONFIRM_PURCHASE button`)
                        return (
                          <div style={{ marginTop: '1rem' }}>
                            <button
                              className="btn-confirm-purchase"
                              onClick={handleOpenPurchaseConfirmation}
                              style={{ width: 'auto', padding: '0.75rem 1.5rem' }}
                            >
                              ✅ Confirm Purchase
                            </button>
                          </div>
                        )
                      }

                      // PRIORITY 2: ADD_CARD button
                      // Show ONLY if:
                      // 1. User expressed purchase intent AND agent confirms AND no card AND cart has items
                      //    (User wants to buy but needs to add card first)
                      //
                      // NEVER show if:
                      // - User hasn't expressed purchase intent (no forcing card onboarding)
                      // - Cart is empty (likely post-purchase confirmation)
                      // - Purchase was just completed (within 30 seconds)
                      if (userExpressedPurchaseIntent && hasPurchaseKeywords && hasCard !== true && hasCartItems) {
                        console.log(`[BUTTON LOGIC] Message ${message.id}: Showing ADD_CARD button (userIntent=${userExpressedPurchaseIntent}, hasPurchaseKeywords=${hasPurchaseKeywords}, hasCard=${hasCard}, hasCartItems=${hasCartItems})`)
                        return (
                          <div style={{ marginTop: '1rem' }}>
                            <button
                              onClick={() => setShowCardForm(true)}
                              style={{
                                background: 'linear-gradient(135deg, #1668e3 0%, #1a1f71 100%)',
                                color: 'white',
                                border: 'none',
                                padding: '0.75rem 1.5rem',
                                borderRadius: '8px',
                                cursor: 'pointer',
                                fontWeight: '500',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                transition: 'all 0.2s',
                                width: 'auto'
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.transform = 'translateY(-1px)'
                                e.currentTarget.style.boxShadow = '0 4px 12px rgba(22, 104, 227, 0.3)'
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.transform = 'translateY(0)'
                                e.currentTarget.style.boxShadow = 'none'
                              }}
                            >
                              <span>💳</span>
                              <span>Add Visa Card with Secure Authentication</span>
                              <span>🔐</span>
                            </button>
                          </div>
                        )
                      }

                      // No button to show
                      console.log(`[BUTTON LOGIC] Message ${message.id}: No button to show`)
                      return null
                    })()}
                    
                    {/* Purchase Confirmation UI */}
                    {message.purchaseConfirmation && message.purchaseConfirmation.requires_confirmation && (
                      <div className="purchase-confirmation-card">
                        <div className="purchase-summary">
                          <h4>🛒 Confirm Purchase</h4>
                          <div className="purchase-details">
                            <div className="purchase-detail-row">
                              <span>Items:</span>
                              <strong>{message.purchaseConfirmation.items_count}</strong>
                            </div>
                            <div className="purchase-detail-row">
                              <span>Total:</span>
                              <strong>{message.purchaseConfirmation.total_amount}</strong>
                            </div>
                            <div className="purchase-detail-row">
                              <span>Payment:</span>
                              <strong>{message.purchaseConfirmation.payment_method}</strong>
                            </div>
                          </div>
                        </div>
                        <div className="purchase-actions">
                          <button 
                            className="btn-confirm-purchase"
                            onClick={() => handleSendMessage('Yes, confirm the purchase')}
                          >
                            ✓ Confirm Purchase
                          </button>
                          <button 
                            className="btn-cancel-purchase"
                            onClick={() => handleSendMessage('No, cancel the purchase')}
                          >
                            ✗ Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                
                {message.role === 'assistant' && (
                  <div className="message-actions-below">
                    <button
                      className="action-btn copy-btn"
                      onClick={() => copyToClipboard(message.content, message.id)}
                      title="Copy message"
                    >
                      {copiedMessageId === message.id ? (
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                          <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                          <path d="M12.668 10.667C12.668 9.95614 12.668 9.46258 12.6367 9.0791C12.6137 8.79732 12.5758 8.60761 12.5244 8.46387L12.4688 8.33399C12.3148 8.03193 12.0803 7.77885 11.793 7.60254L11.666 7.53125C11.508 7.45087 11.2963 7.39395 10.9209 7.36328C10.5374 7.33197 10.0439 7.33203 9.33301 7.33203H6.5C5.78896 7.33203 5.29563 7.33195 4.91211 7.36328C4.63016 7.38632 4.44065 7.42413 4.29688 7.47559L4.16699 7.53125C3.86488 7.68518 3.61186 7.9196 3.43555 8.20703L3.36524 8.33399C3.28478 8.49198 3.22795 8.70352 3.19727 9.0791C3.16595 9.46259 3.16504 9.95611 3.16504 10.667V13.5C3.16504 14.211 3.16593 14.7044 3.19727 15.0879C3.22797 15.4636 3.28473 15.675 3.36524 15.833L3.43555 15.959C3.61186 16.2466 3.86474 16.4807 4.16699 16.6348L4.29688 16.6914C4.44063 16.7428 4.63025 16.7797 4.91211 16.8027C5.29563 16.8341 5.78896 16.835 6.5 16.835H9.33301C10.0439 16.835 10.5374 16.8341 10.9209 16.8027C11.2965 16.772 11.508 16.7152 11.666 16.6348L11.793 16.5645C12.0804 16.3881 12.3148 16.1351 12.4688 15.833L12.5244 15.7031C12.5759 15.5594 12.6137 15.3698 12.6367 15.0879C12.6681 14.7044 12.668 14.211 12.668 13.5V10.667ZM13.998 12.665C14.4528 12.6634 14.8011 12.6602 15.0879 12.6367C15.4635 12.606 15.675 12.5492 15.833 12.4688L15.959 12.3975C16.2466 12.2211 16.4808 11.9682 16.6348 11.666L16.6914 11.5361C16.7428 11.3924 16.7797 11.2026 16.8027 10.9209C16.8341 10.5374 16.835 10.0439 16.835 9.33301V6.5C16.835 5.78896 16.8341 5.29563 16.8027 4.91211C16.7797 4.63025 16.7428 4.44063 16.6914 4.29688L16.6348 4.16699C16.4807 3.86474 16.2466 3.61186 15.959 3.43555L15.833 3.36524C15.675 3.28473 15.4636 3.22797 15.0879 3.19727C14.7044 3.16593 14.211 3.16504 13.5 3.16504H10.667C9.9561 3.16504 9.46259 3.16595 9.0791 3.19727C8.79739 3.22028 8.6076 3.2572 8.46387 3.30859L8.33399 3.36524C8.03176 3.51923 7.77886 3.75343 7.60254 4.04102L7.53125 4.16699C7.4508 4.32498 7.39397 4.53655 7.36328 4.91211C7.33985 5.19893 7.33562 5.54719 7.33399 6.00195H9.33301C10.022 6.00195 10.5791 6.00131 11.0293 6.03809C11.4873 6.07551 11.8937 6.15471 12.2705 6.34668L12.4883 6.46875C12.984 6.7728 13.3878 7.20854 13.6533 7.72949L13.7197 7.87207C13.8642 8.20859 13.9292 8.56974 13.9619 8.9707C13.9987 9.42092 13.998 9.97799 13.998 10.667V12.665ZM18.165 9.33301C18.165 10.022 18.1657 10.5791 18.1289 11.0293C18.0961 11.4302 18.0311 11.7914 17.8867 12.1279L17.8203 12.2705C17.5549 12.7914 17.1509 13.2272 16.6553 13.5313L16.4365 13.6533C16.0599 13.8452 15.6541 13.9245 15.1963 13.9619C14.8593 13.9895 14.4624 13.9935 13.9951 13.9951C13.9935 14.4624 13.9895 14.8593 13.9619 15.1963C13.9292 15.597 13.864 15.9576 13.7197 16.2939L13.6533 16.4365C13.3878 16.9576 12.9841 17.3941 12.4883 17.6982L12.2705 17.8203C11.8937 18.0123 11.4873 18.0915 11.0293 18.1289C10.5791 18.1657 10.022 18.165 9.33301 18.165H6.5C5.81091 18.165 5.25395 18.1657 4.80371 18.1289C4.40306 18.0962 4.04235 18.031 3.70606 17.8867L3.56348 17.8203C3.04244 17.5548 2.60585 17.151 2.30176 16.6553L2.17969 16.4365C1.98788 16.0599 1.90851 15.6541 1.87109 15.1963C1.83431 14.746 1.83496 14.1891 1.83496 13.5V10.667C1.83496 9.978 1.83432 9.42091 1.87109 8.9707C1.90851 8.5127 1.98772 8.10625 2.17969 7.72949L2.30176 7.51172C2.60586 7.0159 3.04236 6.6122 3.56348 6.34668L3.70606 6.28027C4.04237 6.136 4.40303 6.07083 4.80371 6.03809C5.14051 6.01057 5.53708 6.00551 6.00391 6.00391C6.00551 5.53708 6.01057 5.14051 6.03809 4.80371C6.0755 4.34588 6.15483 3.94012 6.34668 3.56348L6.46875 3.34473C6.77282 2.84912 7.20856 2.44514 7.72949 2.17969L7.87207 2.11328C8.20855 1.96886 8.56979 1.90385 8.9707 1.87109C9.42091 1.83432 9.978 1.83496 10.667 1.83496H13.5C14.1891 1.83496 14.746 1.83431 15.1963 1.87109C15.6541 1.90851 16.0599 1.98788 16.4365 2.17969L16.6553 2.30176C17.151 2.60585 17.5548 3.04244 17.8203 3.56348L17.8867 3.70606C18.031 4.04235 18.0962 4.40306 18.1289 4.80371C18.1657 5.25395 18.165 5.81091 18.165 6.5V9.33301Z"></path>
                        </svg>
                      )}
                    </button>
                    
                    {/* Enhanced thumbs up button with visual feedback state */}
                    <button
                      className={`action-btn thumbs-up-btn ${
                        currentFeedback?.feedback === 'up' ? 'feedback-active' : ''
                      } ${currentFeedback?.feedback === 'up' && currentFeedback?.comment ? 'has-comment' : ''} ${
                        submittingFeedback === message.id ? 'feedback-loading' : ''
                      }`}
                      onClick={() => handleFeedback(message.id, 'up')}
                      disabled={submittingFeedback === message.id}
                      title={currentFeedback?.feedback === 'up' ? 'You liked this response' : 'Good response'}
                    >
                      {submittingFeedback === message.id ? (
                        <div className="loading-spinner-small"></div>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                          <path d="M10.9153 1.83987L11.2942 1.88772L11.4749 1.91507C13.2633 2.24201 14.4107 4.01717 13.9749 5.78225L13.9261 5.95901L13.3987 7.6719C13.7708 7.67575 14.0961 7.68389 14.3792 7.70608C14.8737 7.74486 15.3109 7.82759 15.7015 8.03323L15.8528 8.11819C16.5966 8.56353 17.1278 9.29625 17.3167 10.1475L17.347 10.3096C17.403 10.69 17.3647 11.0832 17.2835 11.5098C17.2375 11.7517 17.1735 12.0212 17.096 12.3233L16.8255 13.3321L16.4456 14.7276C16.2076 15.6001 16.0438 16.2356 15.7366 16.7305L15.595 16.9346C15.2989 17.318 14.9197 17.628 14.4866 17.8408L14.2982 17.9258C13.6885 18.1774 12.9785 18.1651 11.9446 18.1651H7.33331C6.64422 18.1651 6.08726 18.1657 5.63702 18.1289C5.23638 18.0962 4.87565 18.031 4.53936 17.8867L4.39679 17.8203C3.87576 17.5549 3.43916 17.151 3.13507 16.6553L3.013 16.4366C2.82119 16.0599 2.74182 15.6541 2.7044 15.1963C2.66762 14.7461 2.66827 14.1891 2.66827 13.5V11.667C2.66827 10.9349 2.66214 10.4375 2.77569 10.0137L2.83722 9.81253C3.17599 8.81768 3.99001 8.05084 5.01397 7.77639L5.17706 7.73928C5.56592 7.66435 6.02595 7.66799 6.66632 7.66799C6.9429 7.66799 7.19894 7.52038 7.33624 7.2803L10.2562 2.16995L10.3118 2.08792C10.4544 1.90739 10.6824 1.81092 10.9153 1.83987ZM7.33136 14.167C7.33136 14.9841 7.33714 15.2627 7.39386 15.4746L7.42999 15.5918C7.62644 16.1686 8.09802 16.6134 8.69171 16.7725L8.87042 16.8067C9.07652 16.8323 9.38687 16.835 10.0003 16.835H11.9446C13.099 16.835 13.4838 16.8228 13.7903 16.6963L13.8997 16.6465C14.1508 16.5231 14.3716 16.3444 14.5433 16.1221L14.6155 16.0166C14.7769 15.7552 14.8968 15.3517 15.1624 14.378L15.5433 12.9824L15.8079 11.9922C15.8804 11.7102 15.9368 11.4711 15.9769 11.2608C16.0364 10.948 16.0517 10.7375 16.0394 10.5791L16.0179 10.4356C15.9156 9.97497 15.641 9.57381 15.2542 9.31253L15.0814 9.20999C14.9253 9.12785 14.6982 9.06544 14.2747 9.03225C13.8477 8.99881 13.2923 8.99807 12.5003 8.99807C12.2893 8.99807 12.0905 8.89822 11.9651 8.72854C11.8398 8.55879 11.8025 8.33942 11.8646 8.13772L12.6556 5.56741L12.7054 5.36331C12.8941 4.35953 12.216 3.37956 11.1878 3.2178L8.49054 7.93948C8.23033 8.39484 7.81431 8.72848 7.33136 8.88967V14.167ZM3.99835 13.5C3.99835 14.2111 3.99924 14.7044 4.03058 15.0879C4.06128 15.4636 4.11804 15.675 4.19854 15.833L4.26886 15.959C4.44517 16.2466 4.69805 16.4808 5.0003 16.6348L5.13019 16.6905C5.27397 16.7419 5.46337 16.7797 5.74542 16.8028C5.97772 16.8217 6.25037 16.828 6.58722 16.8311C6.41249 16.585 6.27075 16.3136 6.1712 16.0215L6.10968 15.8194C5.99614 15.3956 6.00128 14.899 6.00128 14.167V9.00296C5.79386 9.0067 5.65011 9.01339 5.53741 9.02737L5.3587 9.06057C4.76502 9.21965 4.29247 9.66448 4.09601 10.2412L4.06085 10.3584C4.00404 10.5705 3.99835 10.8493 3.99835 11.667V13.5Z"></path>
                        </svg>
                      )}
                    </button>
                    
                    {/* Enhanced thumbs down button with visual feedback state */}
                    <button
                      className={`action-btn thumbs-down-btn ${
                        currentFeedback?.feedback === 'down' ? 'feedback-active' : ''
                      } ${currentFeedback?.feedback === 'down' && currentFeedback?.comment ? 'has-comment' : ''} ${
                        submittingFeedback === message.id ? 'feedback-loading' : ''
                      }`}
                      onClick={() => handleFeedback(message.id, 'down')}
                      disabled={submittingFeedback === message.id}
                      title={currentFeedback?.feedback === 'down' ? 'You disliked this response' : 'Poor response'}
                    >
                      {submittingFeedback === message.id ? (
                        <div className="loading-spinner-small"></div>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" style={{transform: 'rotate(180deg)'}}>
                          <path d="M10.9153 1.83987L11.2942 1.88772L11.4749 1.91507C13.2633 2.24201 14.4107 4.01717 13.9749 5.78225L13.9261 5.95901L13.3987 7.6719C13.7708 7.67575 14.0961 7.68389 14.3792 7.70608C14.8737 7.74486 15.3109 7.82759 15.7015 8.03323L15.8528 8.11819C16.5966 8.56353 17.1278 9.29625 17.3167 10.1475L17.347 10.3096C17.403 10.69 17.3647 11.0832 17.2835 11.5098C17.2375 11.7517 17.1735 12.0212 17.096 12.3233L16.8255 13.3321L16.4456 14.7276C16.2076 15.6001 16.0438 16.2356 15.7366 16.7305L15.595 16.9346C15.2989 17.318 14.9197 17.628 14.4866 17.8408L14.2982 17.9258C13.6885 18.1774 12.9785 18.1651 11.9446 18.1651H7.33331C6.64422 18.1651 6.08726 18.1657 5.63702 18.1289C5.23638 18.0962 4.87565 18.031 4.53936 17.8867L4.39679 17.8203C3.87576 17.5549 3.43916 17.151 3.13507 16.6553L3.013 16.4366C2.82119 16.0599 2.74182 15.6541 2.7044 15.1963C2.66762 14.7461 2.66827 14.1891 2.66827 13.5V11.667C2.66827 10.9349 2.66214 10.4375 2.77569 10.0137L2.83722 9.81253C3.17599 8.81768 3.99001 8.05084 5.01397 7.77639L5.17706 7.73928C5.56592 7.66435 6.02595 7.66799 6.66632 7.66799C6.9429 7.66799 7.19894 7.52038 7.33624 7.2803L10.2562 2.16995L10.3118 2.08792C10.4544 1.90739 10.6824 1.81092 10.9153 1.83987ZM7.33136 14.167C7.33136 14.9841 7.33714 15.2627 7.39386 15.4746L7.42999 15.5918C7.62644 16.1686 8.09802 16.6134 8.69171 16.7725L8.87042 16.8067C9.07652 16.8323 9.38687 16.835 10.0003 16.835H11.9446C13.099 16.835 13.4838 16.8228 13.7903 16.6963L13.8997 16.6465C14.1508 16.5231 14.3716 16.3444 14.5433 16.1221L14.6155 16.0166C14.7769 15.7552 14.8968 15.3517 15.1624 14.378L15.5433 12.9824L15.8079 11.9922C15.8804 11.7102 15.9368 11.4711 15.9769 11.2608C16.0364 10.948 16.0517 10.7375 16.0394 10.5791L16.0179 10.4356C15.9156 9.97497 15.641 9.57381 15.2542 9.31253L15.0814 9.20999C14.9253 9.12785 14.6982 9.06544 14.2747 9.03225C13.8477 8.99881 13.2923 8.99807 12.5003 8.99807C12.2893 8.99807 12.0905 8.89822 11.9651 8.72854C11.8398 8.55879 11.8025 8.33942 11.8646 8.13772L12.6556 5.56741L12.7054 5.36331C12.8941 4.35953 12.216 3.37956 11.1878 3.2178L8.49054 7.93948C8.23033 8.39484 7.81431 8.72848 7.33136 8.88967V14.167ZM3.99835 13.5C3.99835 14.2111 3.99924 14.7044 4.03058 15.0879C4.06128 15.4636 4.11804 15.675 4.19854 15.833L4.26886 15.959C4.44517 16.2466 4.69805 16.4808 5.0003 16.6348L5.13019 16.6905C5.27397 16.7419 5.46337 16.7797 5.74542 16.8028C5.97772 16.8217 6.25037 16.828 6.58722 16.8311C6.41249 16.585 6.27075 16.3136 6.1712 16.0215L6.10968 15.8194C5.99614 15.3956 6.00128 14.899 6.00128 14.167V9.00296C5.79386 9.0067 5.65011 9.01339 5.53741 9.02737L5.3587 9.06057C4.76502 9.21965 4.29247 9.66448 4.09601 10.2412L4.06085 10.3584C4.00404 10.5705 3.99835 10.8493 3.99835 11.667V13.5Z"></path>
                        </svg>
                      )}
                    </button>
                    
                    {!currentFeedback && (
                      <button
                        className="action-btn comment-btn"
                        onClick={() => {
                          setShowCommentBox(message.id)
                          setFeedbackType(null) // Don't default to any feedback type
                          setFeedbackComment('')
                        }}
                        title="Add comment with feedback"
                      >
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                          <path d="M18 5v8a2 2 0 01-2 2h-5l-5 4v-4H4a2 2 0 01-2-2V5a2 2 0 012-2h12a2 2 0 012 2zM7 8H5v2h2V8zm2 0h2v2H9V8zm6 0h-2v2h2V8z"/>
                        </svg>
                      </button>
                    )}
                  </div>
                )}
                
                {/* Minimal comment input for feedback */}
                {showCommentBox === message.id && (
                  <div className="minimal-comment-box">
                    <div className="minimal-feedback-selector">
                      <button
                        className={`minimal-feedback-btn ${feedbackType === 'up' ? 'active' : ''}`}
                        onClick={() => setFeedbackType('up')}
                        title="Helpful"
                      >
                        <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                          <path d="M10.9153 1.83987L11.2942 1.88772L11.4749 1.91507C13.2633 2.24201 14.4107 4.01717 13.9749 5.78225L13.9261 5.95901L13.3987 7.6719C13.7708 7.67575 14.0961 7.68389 14.3792 7.70608C14.8737 7.74486 15.3109 7.82759 15.7015 8.03323L15.8528 8.11819C16.5966 8.56353 17.1278 9.29625 17.3167 10.1475L17.347 10.3096C17.403 10.69 17.3647 11.0832 17.2835 11.5098C17.2375 11.7517 17.1735 12.0212 17.096 12.3233L16.8255 13.3321L16.4456 14.7276C16.2076 15.6001 16.0438 16.2356 15.7366 16.7305L15.595 16.9346C15.2989 17.318 14.9197 17.628 14.4866 17.8408L14.2982 17.9258C13.6885 18.1774 12.9785 18.1651 11.9446 18.1651H7.33331C6.64422 18.1651 6.08726 18.1657 5.63702 18.1289C5.23638 18.0962 4.87565 18.031 4.53936 17.8867L4.39679 17.8203C3.87576 17.5549 3.43916 17.151 3.13507 16.6553L3.013 16.4366C2.82119 16.0599 2.74182 15.6541 2.7044 15.1963C2.66762 14.7461 2.66827 14.1891 2.66827 13.5V11.667C2.66827 10.9349 2.66214 10.4375 2.77569 10.0137L2.83722 9.81253C3.17599 8.81768 3.99001 8.05084 5.01397 7.77639L5.17706 7.73928C5.56592 7.66435 6.02595 7.66799 6.66632 7.66799C6.9429 7.66799 7.19894 7.52038 7.33624 7.2803L10.2562 2.16995L10.3118 2.08792C10.4544 1.90739 10.6824 1.81092 10.9153 1.83987ZM7.33136 14.167C7.33136 14.9841 7.33714 15.2627 7.39386 15.4746L7.42999 15.5918C7.62644 16.1686 8.09802 16.6134 8.69171 16.7725L8.87042 16.8067C9.07652 16.8323 9.38687 16.835 10.0003 16.835H11.9446C13.099 16.835 13.4838 16.8228 13.7903 16.6963L13.8997 16.6465C14.1508 16.5231 14.3716 16.3444 14.5433 16.1221L14.6155 16.0166C14.7769 15.7552 14.8968 15.3517 15.1624 14.378L15.5433 12.9824L15.8079 11.9922C15.8804 11.7102 15.9368 11.4711 15.9769 11.2608C16.0364 10.948 16.0517 10.7375 16.0394 10.5791L16.0179 10.4356C15.9156 9.97497 15.641 9.57381 15.2542 9.31253L15.0814 9.20999C14.9253 9.12785 14.6982 9.06544 14.2747 9.03225C13.8477 8.99881 13.2923 8.99807 12.5003 8.99807C12.2893 8.99807 12.0905 8.89822 11.9651 8.72854C11.8398 8.55879 11.8025 8.33942 11.8646 8.13772L12.6556 5.56741L12.7054 5.36331C12.8941 4.35953 12.216 3.37956 11.1878 3.2178L8.49054 7.93948C8.23033 8.39484 7.81431 8.72848 7.33136 8.88967V14.167ZM3.99835 13.5C3.99835 14.2111 3.99924 14.7044 4.03058 15.0879C4.06128 15.4636 4.11804 15.675 4.19854 15.833L4.26886 15.959C4.44517 16.2466 4.69805 16.4808 5.0003 16.6348L5.13019 16.6905C5.27397 16.7419 5.46337 16.7797 5.74542 16.8028C5.97772 16.8217 6.25037 16.828 6.58722 16.8311C6.41249 16.585 6.27075 16.3136 6.1712 16.0215L6.10968 15.8194C5.99614 15.3956 6.00128 14.899 6.00128 14.167V9.00296C5.79386 9.0067 5.65011 9.01339 5.53741 9.02737L5.3587 9.06057C4.76502 9.21965 4.29247 9.66448 4.09601 10.2412L4.06085 10.3584C4.00404 10.5705 3.99835 10.8493 3.99835 11.667V13.5Z"></path>
                        </svg>
                      </button>
                      <button
                        className={`minimal-feedback-btn ${feedbackType === 'down' ? 'active' : ''}`}
                        onClick={() => setFeedbackType('down')}
                        title="Not helpful"
                      >
                        <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" style={{transform: 'rotate(180deg)'}}>
                          <path d="M10.9153 1.83987L11.2942 1.88772L11.4749 1.91507C13.2633 2.24201 14.4107 4.01717 13.9749 5.78225L13.9261 5.95901L13.3987 7.6719C13.7708 7.67575 14.0961 7.68389 14.3792 7.70608C14.8737 7.74486 15.3109 7.82759 15.7015 8.03323L15.8528 8.11819C16.5966 8.56353 17.1278 9.29625 17.3167 10.1475L17.347 10.3096C17.403 10.69 17.3647 11.0832 17.2835 11.5098C17.2375 11.7517 17.1735 12.0212 17.096 12.3233L16.8255 13.3321L16.4456 14.7276C16.2076 15.6001 16.0438 16.2356 15.7366 16.7305L15.595 16.9346C15.2989 17.318 14.9197 17.628 14.4866 17.8408L14.2982 17.9258C13.6885 18.1774 12.9785 18.1651 11.9446 18.1651H7.33331C6.64422 18.1651 6.08726 18.1657 5.63702 18.1289C5.23638 18.0962 4.87565 18.031 4.53936 17.8867L4.39679 17.8203C3.87576 17.5549 3.43916 17.151 3.13507 16.6553L3.013 16.4366C2.82119 16.0599 2.74182 15.6541 2.7044 15.1963C2.66762 14.7461 2.66827 14.1891 2.66827 13.5V11.667C2.66827 10.9349 2.66214 10.4375 2.77569 10.0137L2.83722 9.81253C3.17599 8.81768 3.99001 8.05084 5.01397 7.77639L5.17706 7.73928C5.56592 7.66435 6.02595 7.66799 6.66632 7.66799C6.9429 7.66799 7.19894 7.52038 7.33624 7.2803L10.2562 2.16995L10.3118 2.08792C10.4544 1.90739 10.6824 1.81092 10.9153 1.83987ZM7.33136 14.167C7.33136 14.9841 7.33714 15.2627 7.39386 15.4746L7.42999 15.5918C7.62644 16.1686 8.09802 16.6134 8.69171 16.7725L8.87042 16.8067C9.07652 16.8323 9.38687 16.835 10.0003 16.835H11.9446C13.099 16.835 13.4838 16.8228 13.7903 16.6963L13.8997 16.6465C14.1508 16.5231 14.3716 16.3444 14.5433 16.1221L14.6155 16.0166C14.7769 15.7552 14.8968 15.3517 15.1624 14.378L15.5433 12.9824L15.8079 11.9922C15.8804 11.7102 15.9368 11.4711 15.9769 11.2608C16.0364 10.948 16.0517 10.7375 16.0394 10.5791L16.0179 10.4356C15.9156 9.97497 15.641 9.57381 15.2542 9.31253L15.0814 9.20999C14.9253 9.12785 14.6982 9.06544 14.2747 9.03225C13.8477 8.99881 13.2923 8.99807 12.5003 8.99807C12.2893 8.99807 12.0905 8.89822 11.9651 8.72854C11.8398 8.55879 11.8025 8.33942 11.8646 8.13772L12.6556 5.56741L12.7054 5.36331C12.8941 4.35953 12.216 3.37956 11.1878 3.2178L8.49054 7.93948C8.23033 8.39484 7.81431 8.72848 7.33136 8.88967V14.167ZM3.99835 13.5C3.99835 14.2111 3.99924 14.7044 4.03058 15.0879C4.06128 15.4636 4.11804 15.675 4.19854 15.833L4.26886 15.959C4.44517 16.2466 4.69805 16.4808 5.0003 16.6348L5.13019 16.6905C5.27397 16.7419 5.46337 16.7797 5.74542 16.8028C5.97772 16.8217 6.25037 16.828 6.58722 16.8311C6.41249 16.585 6.27075 16.3136 6.1712 16.0215L6.10968 15.8194C5.99614 15.3956 6.00128 14.899 6.00128 14.167V9.00296C5.79386 9.0067 5.65011 9.01339 5.53741 9.02737L5.3587 9.06057C4.76502 9.21965 4.29247 9.66448 4.09601 10.2412L4.06085 10.3584C4.00404 10.5705 3.99835 10.8493 3.99835 11.667V13.5Z"></path>
                        </svg>
                      </button>
                    </div>
                    <input
                      type="text"
                      value={feedbackComment}
                      onChange={(e) => setFeedbackComment(e.target.value)}
                      placeholder="Add a comment (optional)..."
                      className="minimal-comment-input"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          submitFeedbackWithComment()
                        } else if (e.key === 'Escape') {
                          cancelFeedback()
                        }
                      }}
                      autoFocus
                    />
                    <div className="minimal-comment-actions">
                      <button onClick={cancelFeedback} className="minimal-cancel-btn">✕</button>
                      <button 
                        onClick={submitFeedbackWithComment}
                        disabled={!feedbackType || submittingFeedback === message.id}
                        className="minimal-submit-btn"
                      >
                        ✓
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-100 bg-white">
          <form className="flex gap-3" onSubmit={sendMessage}>
            <textarea
              ref={textareaRef}
              className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-base outline-none resize-none focus:border-[#1668e3] focus:ring-2 focus:ring-[#1668e3]/10 transition-all"
              value={inputMessage}
              onChange={(e) => {
                setInputMessage(e.target.value)
                autoResizeTextarea(e.target)
              }}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
              disabled={loading}
              rows={1}
            />
            <button 
              type="submit" 
              className="p-3 bg-[#1a1f71] text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all self-end"
              disabled={!inputMessage.trim() || loading}
              title={loading ? 'Processing...' : 'Send message'}
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13"/>
                </svg>
              )}
            </button>
          </form>
        </div>
      </div>
      
      {showCardForm && (
        <div className="card-onboarding-overlay">
          <div className="card-onboarding-form" style={{ maxWidth: '450px', padding: '2rem' }}>
            <CardOnboarding
              userEmail={user.email || `${user.username}@example.com`}
              onComplete={async (result) => {
                console.log('✅ Card onboarding complete:', result)

                try {
                  // Save card to user profile in DynamoDB with VIC session IDs
                  await userProfileService.addPaymentCard(user.userId, {
                    vProvisionedTokenId: result.vProvisionedTokenId,
                    lastFour: result.lastFour,
                    type: result.type,
                    expirationDate: result.expirationDate,
                    cardholderName: result.cardholderName,
                    isPrimary: true,
                    // VIC session IDs needed for purchase flow
                    consumerId: result.consumerId,
                    clientDeviceId: result.clientDeviceId,
                    clientReferenceId: result.clientReferenceId
                  })
                  console.log('💳 Card saved to user profile with VIC session IDs')

                  // Show success toast
                  showToast.success(`Card successfully added: ${result.type} ending in ${result.lastFour}`)
                  setShowCardForm(false)

                  // Clear card check cache to force re-check of all messages
                  // This will cause existing messages with purchase keywords to re-check card status
                  // and update from ADD_CARD button to CONFIRM_PURCHASE button
                  console.log('🔄 Clearing card check cache to force button update')
                  setCardCheckResults({})

                } catch (error) {
                  console.error('❌ Error saving card to profile:', error)
                  // Show error toast
                  showToast.error(`Card added but failed to save to profile: ${result.type} ending in ${result.lastFour}`)
                  setShowCardForm(false)
                }
              }}
              onSkip={() => setShowCardForm(false)}
            />
          </div>
        </div>
      )}

      {showPurchaseConfirmation && (
        <PurchaseConfirmation
          userEmail={user.email || `${user.username}@example.com`}
          userId={user.userId}
          cartItems={purchaseCartItems}
          onComplete={handlePurchaseComplete}
          onError={handlePurchaseError}
          onCancel={handlePurchaseCancel}
        />
      )}

      {visaIframeConfig && (
        <div className="card-onboarding-overlay">
          <div className="card-onboarding-form" style={{ maxWidth: '800px' }}>
            <div className="card-form-header">
              <h3>🔒 Secure Visa Verification</h3>
              <button className="close-btn" onClick={() => setVisaIframeConfig(null)}>×</button>
            </div>
            <VisaIframe
              config={visaIframeConfig}
              onTokenReceived={(token) => {
                handleSendMessage(`Complete Visa onboarding with token: ${token}`)
                setVisaIframeConfig(null)
              }}
              onError={(error) => {
                console.error('Visa iframe error:', error)
                setVisaIframeConfig(null)
                setShowCardForm(true)
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default Chat
