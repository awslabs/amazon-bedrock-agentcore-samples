import { useState, useEffect, useRef } from 'react'
import { userProfileService } from '../services/userProfileService'
import { showToast } from '../utils/toast'

// Use VITE_VISA_PROXY_URL from environment (can be Lambda API Gateway or local server)
// Remove trailing slash to avoid double slashes in URLs
const API_BASE_URL = (import.meta.env.VITE_VISA_PROXY_URL || '').replace(/\/$/, '')

const VISA_IFRAME_URL = import.meta.env.VITE_VISA_IFRAME_URL || 'https://sbx.vts.auth.visa.com'
const API_KEY = import.meta.env.VITE_VISA_API_KEY
const CLIENT_APP_ID = import.meta.env.VITE_VISA_CLIENT_APP_ID

interface PurchaseConfirmationProps {
  userEmail: string
  userId: string
  cartItems: any[]
  onComplete: (result: any) => void
  onError: (error: string) => void
  onCancel: () => void
}

interface IframeMessage {
  type: string
  requestID?: string
  sessionContext?: {
    secureToken: string
  }
  assuranceData?: {
    fidoBlob: string
  }
  [key: string]: any
}

const PurchaseConfirmation = ({ userEmail, userId, cartItems, onComplete, onError, onCancel }: PurchaseConfirmationProps) => {
  const [step, setStep] = useState<'loading' | 'iframe-auth' | 'processing' | 'complete'>('loading')
  const [statusMessage, setStatusMessage] = useState('Initializing purchase...')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const requestIDRef = useRef('')

  // Purchase flow state
  const [secureToken, setSecureToken] = useState('')
  const [browserData, setBrowserData] = useState<any>(null)
  const [dfpSessionId, setDfpSessionId] = useState('')
  const [authIdentifier, setAuthIdentifier] = useState('')
  const [fidoBlob, setFidoBlob] = useState('')
  const [vProvisionedTokenId, setVProvisionedTokenId] = useState('')

  // Handle messages from Visa iframe
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      console.log('📬 Message received from:', event.origin, event.data)

      if (!event.origin.includes('auth.visa.com')) {
        console.log('⚠️ Ignoring message from non-Visa origin:', event.origin)
        return
      }

      const data: IframeMessage = event.data
      console.log('📨 Received from Visa iframe:', data)

      if (data.type === 'AUTH_READY') {
        console.log('✅ Iframe ready, requestID:', data.requestID)
        requestIDRef.current = data.requestID || ''
        // Automatically create auth session for purchase
        sendCreateAuthSession(data.requestID || '')
      } else if (data.type === 'AUTH_SESSION_CREATED') {
        console.log('✅ Auth session created for purchase')
        console.log('Full AUTH_SESSION_CREATED data:', JSON.stringify(data, null, 2))

        const token = data.sessionContext?.secureToken || ''
        const browser = data.browserData || null

        // Extract dfpSessionID - it's typically at the top level or in browserData (note capital "ID")
        const dfpSession = data.dfpSessionID || data.browserData?.dfpSessionID || ''

        console.log('Extracted secureToken:', token ? `${token.substring(0, 60)}...` : 'EMPTY')
        console.log('Extracted browserData:', browser)
        console.log('Extracted dfpSessionID:', dfpSession)

        if (!token) {
          console.error('❌ secureToken is empty!')
        }
        if (!dfpSession) {
          console.warn('⚠️ dfpSessionID is empty - this might cause issues')
        }

        setSecureToken(token)
        setBrowserData(browser)
        setDfpSessionId(dfpSession)

        // Now call device_attestation_authenticate to get authIdentifier
        performDeviceAttestation(token, browser, dfpSession)
      } else if (data.assuranceData?.fidoBlob) {
        console.log('✅ Received fidoBlob for purchase')
        setFidoBlob(data.assuranceData.fidoBlob)
        // Now we have everything, initiate purchase
        initiatePurchase(data.assuranceData.fidoBlob)
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [secureToken, browserData, dfpSessionId, vProvisionedTokenId, authIdentifier])

  // Send command to iframe
  const sendCommand = (command: any) => {
    if (iframeRef.current?.contentWindow) {
      console.log('📤 Sending to iframe:', command)
      iframeRef.current.contentWindow.postMessage(command, VISA_IFRAME_URL)
    }
  }

  const sendCreateAuthSession = (reqID: string) => {
    setStep('iframe-auth')
    setStatusMessage('Creating secure session...')
    sendCommand({
      requestID: reqID,
      type: 'CREATE_AUTH_SESSION',
      version: '1',
      client: { id: CLIENT_APP_ID },
      contentType: 'application/json'
    })
  }

  // Step 2: Device Attestation Register (get authIdentifier, endpoint, payload)
  const performDeviceAttestation = async (token: string, browser: any, dfpSession: string) => {
    try {
      setStatusMessage('Verifying device...')
      console.log('🔵 Step 2: Calling device-attestation-register for purchase')
      console.log('Using secureToken:', token ? `${token.substring(0, 40)}...` : 'EMPTY')
      console.log('Using dfpSessionId:', dfpSession)

      // Get enrolled card from AppSync
      const enrolledCard = await userProfileService.getEnrolledCard(userId)
      if (!enrolledCard) {
        throw new Error('No enrolled card found. Please add a payment method first.')
      }

      console.log('✅ Retrieved enrolled card from AppSync:', enrolledCard.vProvisionedTokenId)
      console.log('Card has consumerId:', enrolledCard.consumerId)
      console.log('Card has clientDeviceId:', enrolledCard.clientDeviceId)
      console.log('Card has clientReferenceId:', enrolledCard.clientReferenceId)
      setVProvisionedTokenId(enrolledCard.vProvisionedTokenId)

      // Calculate total amount for this purchase
      const totalAmount = calculateTotal(cartItems)
      console.log('🔍 AMOUNT DEBUG (Frontend):')
      console.log('  Cart items:', cartItems.map(item => ({ title: item.title, price: item.price, qty: item.qty || 1 })))
      console.log('  Calculated totalAmount:', totalAmount)
      console.log('  totalAmount type:', typeof totalAmount)

      const requestBody = {
        email: userEmail,
        vProvisionedTokenId: enrolledCard.vProvisionedTokenId,
        secureToken: token,
        browserData: browser,
        step: 'AUTHENTICATE',  // Uses device_attestation_authenticate (email only)
        xRequestId: enrolledCard.clientReferenceId,  // Reuse clientReferenceId from enrollment
        clientReferenceId: enrolledCard.clientReferenceId,  // VIC transaction ID - reuse from enrollment
        transactionAmount: totalAmount  // Pass actual cart total
      }

      console.log('🔍 Sending to backend:')
      console.log('  transactionAmount:', requestBody.transactionAmount)

      // Call device attestation authenticate to get authentication challenge for purchase
      // Now uses email only (no PAN data needed) - works for purchase flow
      const attestationResponse = await fetch(`${API_BASE_URL}/api/visa/device-attestation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      const attestationData = await attestationResponse.json()
      if (!attestationData.success) {
        throw new Error(attestationData.error || 'Failed to verify device')
      }

      console.log('✅ Device attestation response:', attestationData)

      // Extract auth data from response - try multiple paths
      const authContext = attestationData.authenticationContext ||
                         attestationData.fullResponse?.authenticationContext || {}
      const identifier = authContext.identifier || enrolledCard.vProvisionedTokenId
      const endpoint = authContext.endpoint || ''
      const payload = authContext.payload || ''

      console.log('🔍 Extracted from Visa response:')
      console.log('  authContext keys:', Object.keys(authContext))
      console.log('  identifier:', identifier)
      console.log('  endpoint:', endpoint)
      console.log('  payload length:', payload?.length || 0)
      console.log('  payload preview:', payload?.substring(0, 200) || 'EMPTY')

      // Try to decode the JWT payload to see what amount Visa embedded
      if (payload && payload.includes('.')) {
        try {
          const parts = payload.split('.')
          if (parts.length >= 2) {
            let payloadPart = parts[1]
            // Add padding if needed
            const padding = 4 - payloadPart.length % 4
            if (padding !== 4) {
              payloadPart += '='.repeat(padding)
            }
            const decoded = JSON.parse(atob(payloadPart))
            console.log('🔍 Decoded JWT payload from Visa:')
            console.log('  Full decoded:', decoded)
            if (decoded.authorization_details && decoded.authorization_details[0]) {
              console.log('  authorization_details[0].details:', decoded.authorization_details[0].details)
              console.log('  AMOUNT IN JWT:', decoded.authorization_details[0].details?.amount || 'NOT FOUND')
            }
          }
        } catch (e) {
          console.log('⚠️ Could not decode payload as JWT:', e)
        }
      }

      setAuthIdentifier(identifier)
      console.log('✅ Got authIdentifier:', identifier)

      // Step 3: Get fido blob from iframe
      setStatusMessage('Authenticating payment...')
      console.log('🔵 Step 3: Sending AUTHENTICATE to iframe for fido blob')

      sendCommand({
        requestID: requestIDRef.current,
        version: '1',
        type: 'AUTHENTICATE',
        authenticationContext: {
          endpoint: endpoint,
          identifier: identifier,
          payload: payload,
          action: 'AUTHENTICATE',  // Purchase uses AUTHENTICATE action to verify with existing passkey
          platformType: 'WEB',
          authenticationPreferencesEnabled: {
            responseMode: 'com_visa_web_message',
            responseType: 'code'
          }
        }
      })

    } catch (error: any) {
      console.error('❌ Error in device attestation:', error)
      const errorMessage = error.message || 'Failed to verify device'
      showToast.error(errorMessage)
      onError(errorMessage)
    }
  }

  // Step 4: Initiate Purchase Instructions
  const initiatePurchase = async (fidoBlobData: string) => {
    try {
      setStep('processing')
      setStatusMessage('Processing purchase...')
      console.log('🔵 Step 4: Initiating purchase instructions')

      // Validate we have all required data
      if (!vProvisionedTokenId) {
        throw new Error('Missing vProvisionedTokenId')
      }
      if (!authIdentifier) {
        throw new Error('Missing authIdentifier')
      }
      if (!fidoBlobData) {
        throw new Error('Missing fidoBlob')
      }

      console.log('Purchase data validation:')
      console.log('  vProvisionedTokenId:', vProvisionedTokenId)
      console.log('  authIdentifier:', authIdentifier)
      console.log('  dfpSessionId:', dfpSessionId || 'EMPTY')
      console.log('  fidoBlob length:', fidoBlobData?.length || 0)
      console.log('  userId:', userId)

      // Get enrolled card data from AppSync
      const enrolledCardData = await userProfileService.getEnrolledCard(userId)
      if (!enrolledCardData) {
        throw new Error('No enrolled card found')
      }

      // Build consumer request from cart items
      const consumerRequest = buildConsumerRequest(cartItems)
      console.log('Consumer request:', consumerRequest)

      // Calculate total amount
      const totalAmount = calculateTotal(cartItems)
      console.log('🔍 VIC PURCHASE AMOUNT DEBUG (Step 4: Initiate Purchase):')
      console.log('  Cart items:', cartItems.map(item => ({ title: item.title, price: item.price, qty: item.qty || 1 })))
      console.log('  Calculated totalAmount:', totalAmount)
      console.log('  totalAmount type:', typeof totalAmount)
      console.log('  This will be sent to VIC initiate-purchase (mandates[0].declineThreshold.amount)')

      // Prepare request body with VIC session IDs from enrolled card
      const requestBody = {
        vProvisionedTokenId: vProvisionedTokenId,
        consumerId: enrolledCardData.consumerId,
        clientReferenceId: enrolledCardData.clientReferenceId,
        clientDeviceId: enrolledCardData.clientDeviceId,
        consumerRequest: consumerRequest,
        authIdentifier: authIdentifier,
        dfpSessionId: dfpSessionId,
        fidoBlob: fidoBlobData,
        transactionAmount: totalAmount  // Pass actual cart total
      }

      console.log('📤 Sending to /api/visa/vic/initiate-purchase:')
      console.log('  Keys:', Object.keys(requestBody))
      console.log('  vProvisionedTokenId:', requestBody.vProvisionedTokenId)
      console.log('  authIdentifier:', requestBody.authIdentifier)
      console.log('  dfpSessionId:', requestBody.dfpSessionId || 'EMPTY')
      console.log('  fidoBlob length:', requestBody.fidoBlob?.length || 0)
      console.log('  transactionAmount:', requestBody.transactionAmount)

      // Call initiate purchase
      const purchaseResponse = await fetch(`${API_BASE_URL}/api/visa/vic/initiate-purchase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      const purchaseData = await purchaseResponse.json()
      if (!purchaseData.success) {
        throw new Error(purchaseData.error || 'Failed to initiate purchase')
      }

      console.log('✅ Purchase initiated:', purchaseData)
      const instructionId = purchaseData.instructionId
      const transactionId = instructionId  // Same thing

      // Step 5: Get Payment Credentials
      setStatusMessage('Getting payment credentials...')
      console.log('🔵 Step 5: Getting payment credentials')

      console.log('🔍 VIC PAYMENT CREDENTIALS AMOUNT DEBUG (Step 5: Get Credentials):')
      console.log('  transactionAmount:', totalAmount)
      console.log('  totalAmount type:', typeof totalAmount)
      console.log('  This will be sent to VIC payment-credentials (transactionData[0].transactionAmount.transactionAmount)')

      // totalAmount already calculated above at line 259
      const credentialsResponse = await fetch(`${API_BASE_URL}/api/visa/vic/payment-credentials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instructionId: transactionId,  // From step 4
          vProvisionedTokenId: vProvisionedTokenId,
          merchantUrl: 'https://www.example.com',  // You may want to make this configurable
          merchantName: 'Travel Concierge',
          transactionAmount: totalAmount,
          user_id: userId
        })
      })

      const credentialsData = await credentialsResponse.json()
      if (!credentialsData.success) {
        throw new Error(credentialsData.error || 'Failed to get payment credentials')
      }

      console.log('✅ Payment credentials retrieved!')
      console.log('Signed Payload:', credentialsData.signedPayload)

      // Close iframe session
      sendCommand({
        requestID: requestIDRef.current,
        type: 'CLOSE_AUTH_SESSION',
        version: '1'
      })

      setStep('complete')
      setStatusMessage('Purchase complete!')

      // Return success with payment data
      onComplete({
        success: true,
        instructionId: instructionId,
        signedPayload: credentialsData.signedPayload,
        status: credentialsData.status,
        cartItems: cartItems,
        totalAmount: totalAmount
      })

    } catch (error: any) {
      console.error('❌ Error in purchase flow:', error)
      const errorMessage = error.message || 'Failed to complete purchase'
      showToast.error(errorMessage)
      onError(errorMessage)
    }
  }

  const buildConsumerRequest = (items: any[]): string => {
    // Build a description of what's being purchased
    const itemDescriptions = items.map(item => `${item.title} ($${item.price})`).join(', ')
    return `Purchase from cart: ${itemDescriptions}`
  }

  const calculateTotal = (items: any[]): string => {
    const total = items.reduce((sum, item) => {
      // Handle price ranges like "$200-250" - take the first number
      const priceStr = item.price || '0'
      const match = priceStr.match(/[\d,]+\.?\d*/)
      const price = match ? parseFloat(match[0].replace(/,/g, '')) : 0
      return sum + (price * (item.qty || 1))
    }, 0)
    return total.toFixed(2)
  }

  // Initialize iframe
  useEffect(() => {
    setStatusMessage('Loading secure payment...')
    const iframe = iframeRef.current
    if (iframe) {
      iframe.onload = () => {
        console.log('✅ Visa iframe loaded for purchase')
        setStatusMessage('Waiting for authentication service...')
      }

      iframe.onerror = (error) => {
        console.error('❌ Iframe load error:', error)
        showToast.error('Failed to load payment authentication')
        onError('Failed to load payment authentication')
      }
    }
  }, [])

  const iframeSrc = `${VISA_IFRAME_URL}/vts-auth/authenticate?apiKey=${encodeURIComponent(API_KEY)}&clientAppID=${encodeURIComponent(CLIENT_APP_ID)}`

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-visa-blue to-visa-blue-light">
          <h3 className="text-lg font-semibold text-white">🔐 Secure Purchase</h3>
          <button 
            className="text-white/80 hover:text-white text-2xl font-light leading-none"
            onClick={onCancel}
          >
            ×
          </button>
        </div>

        <div className="p-6">
          <p className="text-center text-gray-600 mb-4">{statusMessage}</p>

          {/* Visa iframe - shown during authentication */}
          <iframe
            ref={iframeRef}
            src={iframeSrc}
            className={`w-full border border-gray-200 rounded-lg my-5 ${step === 'iframe-auth' ? 'h-24 block' : 'h-0 hidden'}`}
            title="Visa Purchase Authentication"
            allow="payment; publickey-credentials-get"
          />

          {/* Loading spinner */}
          {(step === 'loading' || step === 'processing') && (
            <div className="flex justify-center my-5">
              <div className="w-8 h-8 border-2 border-visa-blue/20 border-t-visa-blue rounded-full animate-spin"></div>
            </div>
          )}

          {/* Success */}
          {step === 'complete' && (
            <div className="text-center my-5">
              <div className="text-5xl text-emerald-500">✅</div>
              <p className="text-emerald-500 font-bold mt-2">Payment Authorized!</p>
            </div>
          )}

          {/* Cart summary */}
          {step !== 'complete' && (
            <div className="bg-gray-50 rounded-lg p-4 mt-4">
              <h4 className="font-semibold text-gray-800 mb-3">Order Summary</h4>
              <div className="space-y-2">
                {cartItems.map((item, index) => (
                  <div key={index} className="flex justify-between text-sm text-gray-600">
                    <span className="truncate mr-2">{item.title}</span>
                    <span className="font-medium">{item.price}</span>
                  </div>
                ))}
              </div>
              <div className="flex justify-between mt-4 pt-3 border-t border-gray-200">
                <span className="font-semibold text-gray-800">Total:</span>
                <span className="font-semibold text-visa-blue">${calculateTotal(cartItems)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default PurchaseConfirmation
