import { useEffect, useState } from 'react'
import { Amplify } from 'aws-amplify'
import { Authenticator } from '@aws-amplify/ui-react'
import { getCurrentUser, signOut } from 'aws-amplify/auth'
import Chat from './components/Chat'
import CartPanel from './components/CartPanel'
import TabbedSidebar from './components/TabbedSidebar'
import UserOnboarding from './components/UserOnboarding'
import UserProfile from './components/UserProfile'
import PurchaseConfirmation from './components/PurchaseConfirmation'
import { useSessions } from './hooks/useSessions'
import { useCart } from './hooks/useCart'
import { getCognitoUserInfo, getDisplayName } from './services/cognitoUserService'
import { ensureUserExists } from './services/userService'
import { userProfileService } from './services/userProfileService'
import { removeCartItems } from './services/cartService'
import { createBooking } from './services/bookingsService'
import outputs from '../../amplify_outputs.json'
import '@aws-amplify/ui-react/styles.css'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import { showToast } from './utils/toast'
import './styles/travel-theme.css'

// Configure Amplify with generated outputs
Amplify.configure(outputs)

interface User {
  username: string
  email?: string
  userId: string
  name?: string
}

interface AppWithSessionsProps {
  user: User
  onSignOut: () => void
}

const AppWithSessions = ({ user, onSignOut }: AppWithSessionsProps) => {
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [profileLoading, setProfileLoading] = useState(true)
  const [displayName, setDisplayName] = useState<string>(user.username)
  const [currentMessages, setCurrentMessages] = useState<any[]>([])

  const [triggerMessage, setTriggerMessage] = useState<{ message: string; timestamp: number } | undefined>()
  const [showPurchaseFlow, setShowPurchaseFlow] = useState(false)
  const [purchaseCartItems, setPurchaseCartItems] = useState<any[]>([])
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0)
  
  const {
    sessions,
    currentSession,
    loading,
    error,
    switchToSession,
    startNewConversation,
    getMessages,
    refreshSessions,
    updateCurrentSession
  } = useSessions(user.userId)

  const { refreshCartCount } = useCart(user.userId)

  // Load messages when session changes
  useEffect(() => {
    if (currentSession) {
      getMessages(currentSession.id).then(messages => {
        setCurrentMessages(messages)
      })
    } else {
      setCurrentMessages([])
    }
  }, [currentSession, getMessages])

  // Check if user needs onboarding and get display name
  useEffect(() => {
    const checkUserProfile = async () => {
      try {
        const profile = await userProfileService.getUserProfile(user.userId)
        if (!profile || !profile.onboardingCompleted) {
          setShowOnboarding(true)
        }
        // Set display name from profile, fallback to username
        if (profile && profile.name) {
          setDisplayName(profile.name)
        }
      } catch (error) {
        console.error('Error checking user profile:', error)
        // If profile doesn't exist, show onboarding
        setShowOnboarding(true)
      } finally {
        setProfileLoading(false)
      }
    }

    checkUserProfile()
  }, [user.userId])

  const handleToggleCart = () => {
    setIsCartOpen(!isCartOpen)
    if (!isCartOpen) {
      refreshCartCount() // Refresh cart count when opening cart
    }
  }

  const handleCloseCart = () => {
    setIsCartOpen(false)
  }

  const handleCartUpdate = () => {
    refreshCartCount() // Refresh cart count when items are updated
  }

  const handlePurchaseConfirm = async (cartItems: any[]) => {
    // Start the Visa purchase flow with iframe
    setPurchaseCartItems(cartItems)
    setShowPurchaseFlow(true)
    setIsCartOpen(false)  // Close cart while processing
  }

  const handlePurchaseComplete = async (result: any) => {
    setShowPurchaseFlow(false)

    // Generate order ID
    const orderId = `ORD-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${result.instructionId?.slice(-8) || 'XXXX'}`

    // Create booking records for purchased items
    if (result.cartItems && result.cartItems.length > 0) {
      for (const item of result.cartItems) {
        await createBooking(user.userId, orderId, {
          item_type: item.item_type || 'product',
          title: item.title,
          price: item.price,
          asin: item.asin,
          url: item.url,
          flight_id: item.details?.flight_id,
          origin: item.details?.origin,
          destination: item.details?.destination,
          departure_date: item.details?.departure_date,
          airline: item.details?.airline,
          hotel_id: item.details?.hotel_id,
          city_code: item.details?.city_code,
          rating: item.details?.rating,
          amenities: item.details?.amenities
        })
      }
      console.log(`📋 Created ${result.cartItems.length} booking records`)
    }

    // Remove only the purchased items from cart (not the entire cart)
    try {
      const asins: string[] = []
      const flight_ids: string[] = []
      const hotel_ids: string[] = []

      console.log('🛒 Processing cart items for removal:', result.cartItems)

      for (const item of result.cartItems) {
        console.log('🛒 Processing item:', {
          item_type: item.item_type,
          asin: item.asin,
          flight_id: item.details?.flight_id,
          hotel_id: item.details?.hotel_id,
          details: item.details
        })

        if (item.item_type === 'flight' && item.details?.flight_id) {
          flight_ids.push(item.details.flight_id)
        } else if (item.item_type === 'hotel' && item.details?.hotel_id) {
          hotel_ids.push(item.details.hotel_id)
        } else if (item.asin) {
          asins.push(item.asin)
        }
      }

      console.log('🛒 Identifiers to remove:', { asins, flight_ids, hotel_ids })
      await removeCartItems(user.userId, { asins, flight_ids, hotel_ids })
      console.log('🛒 Purchased items removed from cart')
    } catch (error) {
      console.error('Error removing purchased items from cart:', error)
    }

    // Send confirmation message to chat
    setTriggerMessage({
      message: `Purchase completed successfully! Payment authorized for $${result.totalAmount}. Order ID: ${orderId}`,
      timestamp: Date.now()
    })

    // Refresh cart count and itinerary/bookings
    refreshCartCount()

    // Trigger itinerary and bookings refresh
    setRefreshTrigger(Date.now())

    console.log('✅ Purchase complete - cart and itinerary refreshed')
  }

  const handlePurchaseError = (error: string) => {
    setShowPurchaseFlow(false)

    // Show error toast notification (15 seconds)
    showToast.error(`Purchase failed: ${error}. Please try again or contact support.`)
  }

  const handlePurchaseCancel = () => {
    setShowPurchaseFlow(false)
  }

  const handleOnboardingComplete = () => {
    setShowOnboarding(false)
    // Refresh display name after onboarding
    userProfileService.getUserProfile(user.userId)
      .then(profile => {
        if (profile && profile.name) {
          setDisplayName(profile.name)
        }
      })
      .catch(() => { /* Profile refresh failed silently */ })
  }

  // Show loading while checking profile
  if (profileLoading) {
    return (
      <div className="flex flex-col h-screen">
        <header className="bg-white text-gray-800 px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <div className="flex items-center gap-3">
            <img src="/VISA-Logo-2006.png" alt="Visa" className="h-8" />
            <h1 className="text-xl font-semibold text-[#0a3a7a]">Concierge Agent</h1>
          </div>
        </header>
        <div className="flex-1 flex flex-col items-center justify-center gap-4 text-white">
          <div className="loading-spinner"></div>
          <div>Setting up your profile...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <ToastContainer />

      {showOnboarding && (
        <UserOnboarding user={user} onComplete={handleOnboardingComplete} />
      )}
      
      <UserProfile user={user} isOpen={showProfile} onClose={() => setShowProfile(false)} />

      {showPurchaseFlow && (
        <PurchaseConfirmation
          userEmail={user.email || `${user.username}@example.com`}
          userId={user.userId}
          cartItems={purchaseCartItems}
          onComplete={handlePurchaseComplete}
          onError={handlePurchaseError}
          onCancel={handlePurchaseCancel}
        />
      )}

      {/* Header */}
      <header className="bg-[#1a1f71] text-white px-6 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <img src="/VISA-Logo-2006.png" alt="Visa" className="h-8" />
          <h1 className="text-xl font-semibold">Concierge Agent</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-white/80">Welcome, {displayName}!</span>

          <button
            onClick={() => setShowProfile(true)}
            className="flex items-center gap-2 px-3 py-2 text-white/90 hover:bg-white/10 rounded-lg text-sm font-medium transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            Profile
          </button>
          
          <button 
            onClick={handleToggleCart}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isCartOpen ? 'bg-white text-[#0a3a7a]' : 'text-white/90 hover:bg-white/10'
            }`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3H5L5.4 5M7 13H17L21 5H5.4M7 13L5.4 5M7 13L4.7 15.3C4.3 15.7 4.6 16.5 5.1 16.5H17M17 13V16.5M9 19.5A1.5 1.5 0 1 0 9 22.5A1.5 1.5 0 0 0 9 19.5ZM20 19.5A1.5 1.5 0 1 0 20 22.5A1.5 1.5 0 0 0 20 19.5Z"/>
            </svg>
            {isCartOpen ? 'Close Cart' : 'View Cart'}
          </button>
          
          <button 
            onClick={onSignOut}
            className="px-4 py-2 bg-white/10 hover:bg-white hover:text-[#0a3a7a] border border-white/30 rounded-lg text-sm font-medium transition-colors"
          >
            Sign Out
          </button>
        </div>
      </header>
      
      <CartPanel
        user={user}
        isOpen={isCartOpen}
        onClose={handleCloseCart}
        onCartUpdate={handleCartUpdate}
        onPurchaseConfirm={handlePurchaseConfirm}
        refreshTrigger={refreshTrigger}
      />
      
      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        <Chat
          user={user}
          onSignOut={onSignOut}
          currentSession={currentSession}
          sessions={sessions}
          onSwitchSession={(sessionId) => {
            const session = sessions.find(s => s.id === sessionId)
            if (session) switchToSession(session)
          }}
          getMessages={getMessages}
          refreshSessions={refreshSessions}
          updateCurrentSession={updateCurrentSession}
          onMessagesUpdate={setCurrentMessages}
          triggerMessage={triggerMessage}
          onNewChat={startNewConversation}
          canStartNewChat={!loading}
          onCartUpdate={handleCartUpdate}
        />
        <TabbedSidebar user={user} messages={currentMessages} refreshTrigger={refreshTrigger} />
      </div>
    </div>
  )
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [isConfigured, setIsConfigured] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Amplify is already configured with outputs, just check auth state
    setIsConfigured(true)
    checkAuthState()
  }, [])

  const checkAuthState = async () => {
    try {
      // Clear any stale auth tokens
      const authKeys = Object.keys(localStorage).filter(key => 
        key.includes('CognitoIdentityServiceProvider') || 
        key.includes('amplify')
      )
      // Clear stale tokens if found
      
      const currentUser = await getCurrentUser()
      
      // Ensure user record exists for ChatSession relationship
      await ensureUserExists(currentUser.userId)
      
      // Get user info from Cognito attributes
      const cognitoUserInfo = await getCognitoUserInfo(currentUser.userId)
      const displayName = getDisplayName(cognitoUserInfo)
      
      setUser({
        username: displayName,
        email: cognitoUserInfo.email || currentUser.signInDetails?.loginId,
        userId: currentUser.userId,
        name: cognitoUserInfo.fullName
      })
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSignOut = async () => {
    try {
      await signOut()
      setUser(null)
    } catch {
      // Sign out failed silently
    }
  }

  if (!isConfigured || isLoading) {
    return (
      <div className="App" style={{ padding: '2rem', textAlign: 'center' }}>
        <div>Configuring Amplify...</div>
      </div>
    )
  }

  return (
    <div className="App">
      <Authenticator signUpAttributes={['email', 'given_name', 'family_name']}>
        {({ user: amplifyUser }) => {
          // Update user state when Authenticator provides user
          if (amplifyUser && !user) {
            // Ensure user record exists and get user info from Cognito attributes
            Promise.all([
              ensureUserExists(amplifyUser.userId),
              getCognitoUserInfo(amplifyUser.userId)
            ])
              .then(([_, cognitoUserInfo]) => {
                const displayName = getDisplayName(cognitoUserInfo)
                
                const userData = {
                  username: displayName,
                  email: cognitoUserInfo.email || amplifyUser.signInDetails?.loginId,
                  userId: amplifyUser.userId,
                  name: cognitoUserInfo.fullName
                }
                
                setUser(userData)
              })
              .catch(() => {
                // Fallback to basic user data
                const userData = {
                  username: amplifyUser.username,
                  email: amplifyUser.signInDetails?.loginId,
                  userId: amplifyUser.userId
                }
                setUser(userData)
              })
          } else if (!amplifyUser && user) {
            setUser(null)
          }

          return user ? (
            <AppWithSessions user={user} onSignOut={handleSignOut} />
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <div>Please sign in to continue</div>
            </div>
          )
        }}
      </Authenticator>
    </div>
  )
}

export default App
