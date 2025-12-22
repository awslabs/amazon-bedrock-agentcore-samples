import { useState, useEffect, useRef } from 'react'
import { showToast } from '../utils/toast'
import visaMockService from '../services/visaMockService'

// Use VITE_VISA_PROXY_URL from environment (can be Lambda API Gateway or local server)
// Remove trailing slash to avoid double slashes in URLs
const API_BASE_URL = (import.meta.env.VITE_VISA_PROXY_URL || '').replace(/\/$/, '')

const VISA_IFRAME_URL = import.meta.env.VITE_VISA_IFRAME_URL || 'https://sbx.vts.auth.visa.com'
const API_KEY = import.meta.env.VITE_VISA_API_KEY
const CLIENT_APP_ID = import.meta.env.VITE_VISA_CLIENT_APP_ID
const MOCK_MODE = visaMockService.isEnabled()

// Validate required environment variables (only if not in mock mode)
if (!MOCK_MODE && (!API_KEY || !CLIENT_APP_ID)) {
  console.error('❌ Missing required Visa environment variables: VITE_VISA_API_KEY, VITE_VISA_CLIENT_APP_ID')
}

// Log mode at startup
if (MOCK_MODE) {
  console.log('🎭 VisaIframeAuth: MOCK MODE enabled - Using frontend mock service (no backend server needed)')
} else {
  console.log('🔐 VisaIframeAuth: REAL MODE - Using backend server at', API_BASE_URL)
}

interface VisaIframeAuthProps {
  userEmail: string
  cardData: {
    cardNumber: string
    cardholderName: string
    cvv: string
    expirationMonth: string
    expirationYear: string
  }
  onComplete: (result: any) => void
  onError: (error: string) => void
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

const VisaIframeAuth = ({ userEmail, cardData, onComplete, onError }: VisaIframeAuthProps) => {
  const [step, setStep] = useState<'loading' | 'enrolling' | 'iframe' | 'authenticating' | 'otp' | 'complete'>('loading')
  const [statusMessage, setStatusMessage] = useState('Initializing...')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const requestIDRef = useRef('')  // Use ref instead of state to avoid closure issues
  const [secureToken, setSecureToken] = useState('')
  const [vProvisionedTokenId, setVProvisionedTokenId] = useState('')
  const [browserData, setBrowserData] = useState<any>(null)
  const [xRequestId, setXRequestId] = useState('')  // VPP session x-request-id
  const [clientReferenceId, setClientReferenceId] = useState('')
  const [authIdentifier, setAuthIdentifier] = useState('')  // From device attestation
  const [dfpSessionId, setDfpSessionId] = useState('')  // From iframe
  
  // Use refs to store values that need to be accessed in callbacks (avoid stale closure issues)
  const authIdentifierRef = useRef('')
  const dfpSessionIdRef = useRef('')


  // OTP state management
  const [showOTPModal, setShowOTPModal] = useState(false)
  const [stepUpOptions, setStepUpOptions] = useState<Array<{method: string, value: string, identifier: string}>>([])
  const [selectedStepUpOption, setSelectedStepUpOption] = useState<{method: string, identifier: string} | null>(null)
  const [otpValue, setOtpValue] = useState('')
  const [otpError, setOtpError] = useState('')

  // Handle messages from Visa iframe
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Log ALL messages for debugging
      console.log('📬 Message received from:', event.origin, event.data)

      // Only accept messages from Visa auth domain
      if (!event.origin.includes('auth.visa.com')) {
        console.log('⚠️ Ignoring message from non-Visa origin:', event.origin)
        return
      }

      const data: IframeMessage = event.data
      console.log('📨 Received from Visa iframe:', data)

      if (data.type === 'AUTH_READY') {
        console.log('✅ Iframe ready, requestID:', data.requestID)
        requestIDRef.current = data.requestID || ''
        // Automatically create auth session
        sendCreateAuthSession(data.requestID || '')
      } else if (data.type === 'AUTH_SESSION_CREATED') {
        console.log('✅ Auth session created')
        console.log('Full AUTH_SESSION_CREATED data:', JSON.stringify(data, null, 2))
        const token = data.sessionContext?.secureToken || ''
        const browser = data.browserData || null
        // Extract dfpSessionID - it's typically at the top level or in browserData (note capital "ID")
        const dfpSession = (data as any).dfpSessionID || data.browserData?.dfpSessionID || ''
        console.log('Extracted secureToken:', token ? `${token.substring(0, 60)}...` : 'EMPTY OR NULL')
        console.log('Extracted browserData:', browser)
        console.log('Extracted dfpSessionID:', dfpSession)
        setSecureToken(token)
        setBrowserData(browser)
        setDfpSessionId(dfpSession)
        dfpSessionIdRef.current = dfpSession  // Store in ref for callback access
        // Now enroll card with this secure token and browser data
        enrollCardWithToken(token, browser)
      } else if (data.assuranceData?.fidoBlob) {
        console.log('✅ Received fidoBlob')
        setStep('authenticating')
        setStatusMessage('Completing registration...')
        // Complete passkey registration
        completePasskeyRegistration(data.assuranceData.fidoBlob)
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [vProvisionedTokenId])

  // Send command to iframe
  const sendCommand = (command: any) => {
    if (iframeRef.current?.contentWindow) {
      console.log('📤 Sending to iframe:', command)
      iframeRef.current.contentWindow.postMessage(command, VISA_IFRAME_URL)
    }
  }

  const sendCreateAuthSession = (reqID: string) => {
    sendCommand({
      requestID: reqID,
      type: 'CREATE_AUTH_SESSION',
      version: '1',
      client: { id: CLIENT_APP_ID },
      contentType: 'application/json'
    })
  }

  // OTP handling functions
  const handleStepUpSelection = async (option: {method: string, identifier: string}) => {
    try {
      setSelectedStepUpOption(option)
      setStatusMessage('Sending verification code...')

      // Call step-up endpoint to trigger OTP send
      let data;
      if (MOCK_MODE) {
        data = await visaMockService.stepUp({
          vProvisionedTokenId,
          identifier: option.identifier,
          method: option.method,
          xRequestId,
          clientReferenceId
        });
      } else {
        const response = await fetch(`${API_BASE_URL}/api/visa/step-up`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            vProvisionedTokenId,
            identifier: option.identifier,
            method: option.method,
            xRequestId,  // Pass x_request_id for VPP session continuity
            clientReferenceId  // Pass client_reference_id for transaction tracking
          })
        })

        data = await response.json()
      }
      if (!data.success) {
        throw new Error(data.error || 'Failed to send verification code')
      }

      console.log('✅ Step-up option selected, OTP sent')
      setStatusMessage('Please enter the verification code')
    } catch (error: any) {
      console.error('❌ Error selecting step-up option:', error)
      setOtpError(error.message || 'Failed to send verification code')
    }
  }

  const handleOTPSubmit = async () => {
    try {
      setOtpError('')
      setStatusMessage('Validating code...')

      // Validate OTP
      let data;
      if (MOCK_MODE) {
        data = await visaMockService.validateOtp({
          vProvisionedTokenId,
          otpValue,
          xRequestId,
          clientReferenceId
        });
      } else {
        const response = await fetch(`${API_BASE_URL}/api/visa/validate-otp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            vProvisionedTokenId,
            otpValue,
            xRequestId,  // Pass x_request_id for VPP session continuity
            clientReferenceId  // Pass client_reference_id for transaction tracking
          })
        })

        data = await response.json()
      }
      if (!data.success) {
        throw new Error(data.error || 'Invalid verification code')
      }

      console.log('✅ OTP validated successfully')
      setShowOTPModal(false)

      // Continue to Step 9: Get device attestation options (REGISTER)
      await continueToPasskeyCreation()

    } catch (error: any) {
      console.error('❌ Error validating OTP:', error)
      setOtpError(error.message || 'Invalid verification code')
    }
  }

  const continueToPasskeyCreation = async () => {
    try {
      setStatusMessage('Preparing passkey creation...')

      // Step 9: Get device attestation options (REGISTER)
      let attestationData;
      if (MOCK_MODE) {
        attestationData = await visaMockService.deviceAttestation({
          email: userEmail,
          vProvisionedTokenId,
          secureToken,
          browserData,
          step: 'REGISTER',
          xRequestId,
          clientReferenceId
        });
      } else {
        const attestationResponse = await fetch(`${API_BASE_URL}/api/visa/device-attestation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: userEmail,
            vProvisionedTokenId,
            secureToken,
            browserData,
            step: 'REGISTER',  // This time we want REGISTER, not AUTHENTICATE
            xRequestId,  // Pass x_request_id for VPP session continuity
            clientReferenceId  // Pass client_reference_id for transaction tracking
          })
        })

        attestationData = await attestationResponse.json()
      }
      if (!attestationData.success) {
        throw new Error(attestationData.error || 'Failed to get attestation options')
      }

      console.log('✅ Got device attestation options for REGISTER:', attestationData)

      // Extract and store authIdentifier from device attestation response
      const identifier = attestationData.authenticationContext?.identifier || ''
      console.log('Extracted authIdentifier:', identifier)
      setAuthIdentifier(identifier)
      authIdentifierRef.current = identifier  // Store in ref for callback access

      if (MOCK_MODE) {
        // In mock mode, skip iframe interaction and simulate fidoBlob response
        console.log('🎭 MOCK MODE: Simulating biometric authentication')
        setStatusMessage('Simulating biometric authentication...')
        
        // Generate mock fidoBlob and proceed directly to completion
        const mockFidoBlob = `MOCK-FIDO-BLOB-${Math.random().toString(36).substring(2, 15).toUpperCase()}`
        
        setTimeout(() => {
          completePasskeyRegistration(mockFidoBlob)
        }, 800)
        
        return // Skip iframe interaction
      }

      // Real mode - Send AUTHENTICATE command to iframe with payload from backend
      setStep('iframe')
      setStatusMessage('Please complete biometric authentication...')

      console.log('📤 Sending AUTHENTICATE to iframe for passkey creation')
      sendCommand({
        requestID: requestIDRef.current,
        version: '1',
        type: 'AUTHENTICATE',
        authenticationContext: {
          endpoint: attestationData.authenticationContext?.endpoint || '',
          identifier: attestationData.authenticationContext?.identifier || vProvisionedTokenId,
          payload: attestationData.authenticationContext?.payload || '',
          action: 'REGISTER',
          platformType: 'WEB',
          authenticationPreferencesEnabled: {
            responseMode: 'com_visa_web_message',
            responseType: 'code'
          }
        }
      })

    } catch (error: any) {
      console.error('❌ Error continuing to passkey creation:', error)
      showToast.error('Failed to set up secure authentication. Please try again.')
      onError('Failed to set up secure authentication. Please try again.')
    }
  }

  const enrollCardWithToken = async (token: string, browser: any) => {
    try {
      console.log('🔵 enrollCardWithToken called with token:', token ? `${token.substring(0, 60)}...` : 'EMPTY OR NULL')
      console.log('🔵 enrollCardWithToken called with browserData:', browser)
      setStep('enrolling')
      setStatusMessage('Enrolling your card...')

      // Use mock service if enabled
      let data;
      if (MOCK_MODE) {
        data = await visaMockService.onboardCard({
          email: userEmail,
          cardNumber: cardData.cardNumber.replace(/\s/g, ''),
          cvv: cardData.cvv,
          expirationMonth: cardData.expirationMonth,
          expirationYear: cardData.expirationYear,
          secureToken: token,
          browserData: browser
        });
      } else {
        const response = await fetch(`${API_BASE_URL}/api/visa/onboard-card`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: userEmail,
            cardNumber: cardData.cardNumber.replace(/\s/g, ''),
            cvv: cardData.cvv,
            expirationMonth: cardData.expirationMonth,
            expirationYear: cardData.expirationYear,
            secureToken: token,  // Pass the secure token from iframe CREATE_AUTH_SESSION
            browserData: browser  // Pass the browser data from iframe CREATE_AUTH_SESSION
          })
        })

        data = await response.json()
      }

      if (!data.success) {
        throw new Error(data.error || 'Failed to enroll card')
      }

      console.log('✅ Card enrolled and token provisioned:', data)
      setVProvisionedTokenId(data.vProvisionedTokenId)
      setXRequestId(data.xRequestId)  // Store x_request_id for VPP session continuity
      setClientReferenceId(data.clientReferenceId)  // Store client_reference_id for transaction tracking
      console.log('🔑 Stored x-request-id for VPP session:', data.xRequestId)
      console.log('🔑 Stored client-reference-id for transaction:', data.clientReferenceId)

      // Step 4: Device Attestation Authenticate (check if device binding needed)
      setStatusMessage('Checking device status...')
      console.log('🔵 Step 4: Calling device-attestation (AUTHENTICATE)')

      const panData = JSON.stringify({
        accountNumber: cardData.cardNumber.replace(/\s/g, ''),
        cvv2: cardData.cvv,
        expirationDate: {
          month: cardData.expirationMonth,
          year: cardData.expirationYear
        }
      })

      let attestationAuthData;
      if (MOCK_MODE) {
        attestationAuthData = await visaMockService.deviceAttestation({
          email: userEmail,
          vProvisionedTokenId: data.vProvisionedTokenId,
          secureToken: token,
          browserData: browser,
          step: 'AUTHENTICATE',
          panData,
          xRequestId: data.xRequestId,
          clientReferenceId: data.clientReferenceId
        });
      } else {
        const attestationAuthResponse = await fetch(`${API_BASE_URL}/api/visa/device-attestation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: userEmail,
            vProvisionedTokenId: data.vProvisionedTokenId,
            secureToken: token,
            browserData: browser,
            step: 'AUTHENTICATE',
            panData,
            xRequestId: data.xRequestId,  // Pass x_request_id for VPP session continuity
            clientReferenceId: data.clientReferenceId  // Pass client_reference_id for transaction tracking
          })
        })

        attestationAuthData = await attestationAuthResponse.json()
      }

      if (!attestationAuthData.success) {
        throw new Error(attestationAuthData.error || 'Failed to check device status')
      }

      console.log('✅ Device attestation authenticate:', attestationAuthData)
      console.log('Action:', attestationAuthData.action)

      // Check if device binding is needed
      if (attestationAuthData.action === 'REGISTER') {
        console.log('🔵 Device binding required, proceeding to Step 5')

        // Step 5: Device Binding - get step-up options
        setStatusMessage('Setting up device verification...')
        let deviceBindingData;
        if (MOCK_MODE) {
          deviceBindingData = await visaMockService.deviceBinding({
            vProvisionedTokenId: data.vProvisionedTokenId,
            secureToken: token,
            email: userEmail,
            browserData: browser,
            xRequestId: data.xRequestId,
            clientReferenceId: data.clientReferenceId
          });
        } else {
          const deviceBindingResponse = await fetch(`${API_BASE_URL}/api/visa/device-binding`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              vProvisionedTokenId: data.vProvisionedTokenId,
              secureToken: token,
              email: userEmail,
              browserData: browser,
              xRequestId: data.xRequestId,  // Pass x_request_id for VPP session continuity
              clientReferenceId: data.clientReferenceId  // Pass client_reference_id for transaction tracking
            })
          })

          deviceBindingData = await deviceBindingResponse.json()
        }

        if (!deviceBindingData.success) {
          throw new Error(deviceBindingData.error || 'Failed to get device binding options')
        }

        console.log('✅ Device binding options:', deviceBindingData)

        // Show OTP modal with step-up options
        setStepUpOptions(deviceBindingData.stepUpRequest || [])
        setStep('otp')
        setShowOTPModal(true)
        setStatusMessage('Please verify your identity')

        // Steps 6-8 are handled by OTP modal (handleStepUpSelection, handleOTPSubmit)
        // After OTP validation, continueToPasskeyCreation() is called (Step 9-10)
      } else {
        console.log('⚠️ Unexpected action:', attestationAuthData.action)
        throw new Error('Unexpected device attestation response')
      }

    } catch (error: any) {
      console.error('❌ Error enrolling card:', error)
      // Sanitize error message - don't show API URLs or technical details
      let userMessage = 'Failed to enroll card. Please try again.'
      if (error.message) {
        if (error.message.includes('400')) {
          userMessage = 'Card validation failed. Please check your card details.'
        } else if (error.message.includes('401') || error.message.includes('403')) {
          userMessage = 'Authentication failed. Please contact support.'
        } else if (error.message.includes('500')) {
          userMessage = 'Service temporarily unavailable. Please try again later.'
        }
      }
      showToast.error(userMessage)
      onError(userMessage)
    }
  }

  const completePasskeyRegistration = async (fidoBlob: string) => {
    try {
      // Step 10: Complete passkey registration
      console.log('fidoBlob:', fidoBlob)
      setStatusMessage('Completing passkey registration...')
      console.log('📤 Sending to backend:', {
        vProvisionedTokenId,
        fidoBlobType: typeof fidoBlob,
        fidoBlobLength: fidoBlob?.length,
        fidoBlob: fidoBlob
      })

      let data;
      if (MOCK_MODE) {
        data = await visaMockService.completePasskey({
          vProvisionedTokenId,
          fidoBlob
        });
      } else {
        const response = await fetch(`${API_BASE_URL}/api/visa/complete-passkey`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            vProvisionedTokenId: vProvisionedTokenId,
            fidoBlob: fidoBlob
          })
        })

        data = await response.json()
      }

      if (!data.success) {
        throw new Error(data.error || 'Failed to complete passkey registration')
      }

      console.log('✅ Passkey registration complete!')

      // Step 14: VIC Enroll Card
      setStatusMessage('Enrolling card for payments...')
      console.log('🔵 Step 14: VIC Enroll Card')

      let vicEnrollData;
      if (MOCK_MODE) {
        vicEnrollData = await visaMockService.vicEnrollCard({
          email: userEmail,
          vProvisionedTokenId
        });
      } else {
        const vicEnrollResponse = await fetch(`${API_BASE_URL}/api/visa/vic/enroll-card`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: userEmail,
            vProvisionedTokenId: vProvisionedTokenId
          })
        })

        vicEnrollData = await vicEnrollResponse.json()
      }

      if (!vicEnrollData.success) {
        throw new Error(vicEnrollData.error || 'Failed to enroll card with VIC')
      }

      console.log('✅ VIC card enrolled:', vicEnrollData.clientReferenceId)
      console.log('  consumerId:', vicEnrollData.consumerId)
      console.log('  clientDeviceId:', vicEnrollData.clientDeviceId)
      setClientReferenceId(vicEnrollData.clientReferenceId)

      // Complete!
      setStep('complete')
      setStatusMessage('Card added successfully!')

      // Close iframe session
      sendCommand({
        requestID: requestIDRef.current,  // Use ref to get current value
        type: 'CLOSE_AUTH_SESSION',
        version: '1'
      })

      // Return success with VIC session IDs for purchase flow
      onComplete({
        vProvisionedTokenId: vProvisionedTokenId,
        lastFour: cardData.cardNumber.replace(/\s/g, '').slice(-4),
        type: 'Visa',
        expirationDate: `${cardData.expirationMonth}/${cardData.expirationYear}`,
        cardholderName: cardData.cardholderName,
        // VIC session IDs needed for purchase flow
        consumerId: vicEnrollData.consumerId,
        clientDeviceId: vicEnrollData.clientDeviceId,
        clientReferenceId: vicEnrollData.clientReferenceId
      })

    } catch (error: any) {
      console.error('❌ Error in card onboarding flow:', error)
      showToast.error('Failed to complete card setup. Please try again or contact support.')
      onError('Failed to complete card setup. Please try again or contact support.')
    }
  }

  // Initialize iframe when component mounts OR start mock flow immediately
  useEffect(() => {
    if (MOCK_MODE) {
      // In mock mode, skip iframe and start enrollment immediately
      console.log('🎭 MOCK MODE: Skipping iframe, starting mock enrollment')
      setStatusMessage('Initializing mock enrollment...')
      
      // Generate mock secure token and browser data
      const mockSecureToken = `MOCK-TOKEN-${Math.random().toString(36).substring(2, 15).toUpperCase()}`
      const mockBrowserData = {
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        mock: true
      }
      
      // Start enrollment process immediately with mock data
      setTimeout(() => {
        enrollCardWithToken(mockSecureToken, mockBrowserData)
      }, 500)
      
      return // Exit early, don't set up iframe
    }

    // Real mode - set up iframe
    setStatusMessage('Loading Visa authentication...')
    const iframe = iframeRef.current
    if (iframe) {
      iframe.onload = () => {
        console.log('✅ Visa iframe loaded')
        setStatusMessage('Waiting for authentication service...')
      }

      iframe.onerror = (error) => {
        console.error('❌ Iframe load error:', error)
        showToast.error('Failed to load Visa authentication iframe')
        onError('Failed to load Visa authentication iframe')
      }
    }

    // Timeout warning after 15 seconds
    const timeout = setTimeout(() => {
      console.warn('⚠️ Iframe has not sent AUTH_READY after 15 seconds')
      console.log('Current iframe src:', iframeSrc)
      console.log('Current requestID:', requestIDRef.current)
      console.log('Check browser console for any errors or blocked content')
    }, 15000)

    return () => clearTimeout(timeout)
  }, [])

  const iframeSrc = `${VISA_IFRAME_URL}/vts-auth/authenticate?apiKey=${encodeURIComponent(API_KEY)}&clientAppID=${encodeURIComponent(CLIENT_APP_ID)}`

  return (
    <div className="p-4 bg-gray-50 rounded-lg text-center min-w-[380px]">
      <h3 className="text-lg font-semibold mb-2">🔐 Secure Card Registration</h3>
      <p className="text-gray-500 text-sm mb-3">{statusMessage}</p>

      {/* Visa iframe - only render in real mode */}
      {!MOCK_MODE && (
        <iframe
          ref={iframeRef}
          src={iframeSrc}
          className={`w-full max-w-[380px] mx-auto border-0 rounded-lg bg-white ${
            step === 'iframe' ? 'block h-[380px]' : 'hidden h-0'
          }`}
          title="Visa Authentication"
        />
      )}

      {/* Loading spinner */}
      {(step === 'loading' || step === 'enrolling' || step === 'authenticating') && (
        <div className="inline-block w-10 h-10 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
      )}

      {step === 'complete' && (
        <div className="text-emerald-500 text-5xl">✅</div>
      )}

      {/* OTP Modal */}
      {showOTPModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1000]">
          <div className="bg-white p-6 rounded-lg max-w-[400px] w-[90%] text-center">
            <h3 className="mt-0 font-semibold text-lg">Verify Your Identity</h3>

            {!selectedStepUpOption ? (
              <>
                <p className="text-gray-500 mb-5">
                  Please select how you'd like to receive your verification code:
                </p>
                <div className="flex flex-col gap-2">
                  {stepUpOptions.map((option, index) => (
                    <button
                      key={index}
                      onClick={() => handleStepUpSelection({method: option.method, identifier: option.identifier})}
                      className="px-5 py-3 bg-blue-600 text-white border-none rounded cursor-pointer text-sm hover:bg-blue-700"
                    >
                      {option.method === 'OTPSMS' ? `📱 SMS to ${option.value}` : `📧 Email to ${option.value}`}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <p className="text-gray-500 mb-5">
                  Enter the verification code sent to your {selectedStepUpOption.method === 'OTPSMS' ? 'phone' : 'email'}:
                </p>
                <input
                  type="text"
                  value={otpValue}
                  onChange={(e) => setOtpValue(e.target.value)}
                  placeholder="Enter code"
                  maxLength={6}
                  className="w-full p-3 text-lg text-center border border-gray-300 rounded mb-2 tracking-[8px]"
                />
                {otpError && (
                  <p className="text-red-500 text-sm mb-2">{otpError}</p>
                )}
                <div className="flex gap-2 justify-center">
                  <button
                    onClick={() => {
                      setSelectedStepUpOption(null)
                      setOtpValue('')
                      setOtpError('')
                    }}
                    className="px-5 py-3 bg-gray-500 text-white border-none rounded cursor-pointer hover:bg-gray-600"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleOTPSubmit}
                    disabled={otpValue.length === 0}
                    className={`px-5 py-3 text-white border-none rounded ${
                      otpValue.length === 0 
                        ? 'bg-gray-300 cursor-not-allowed' 
                        : 'bg-emerald-500 cursor-pointer hover:bg-emerald-600'
                    }`}
                  >
                    Verify
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default VisaIframeAuth
