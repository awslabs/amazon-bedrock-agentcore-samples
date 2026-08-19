/**
 * Frontend Mock Visa API Service
 *
 * This service provides mock/fake Visa API responses directly in the browser,
 * eliminating the need to run the local backend server during development.
 *
 * Enable by setting: VITE_VISA_MOCK_MODE=true in .env.local
 */

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const generateMockId = (prefix: string) => {
  return `${prefix}-${Math.random().toString(36).substring(2, 15).toUpperCase()}`;
};

export const visaMockService = {
  /**
   * Check if mock mode is enabled
   */
  isEnabled(): boolean {
    return import.meta.env.VITE_VISA_MOCK_MODE === 'true';
  },

  /**
   * Mock: Get secure token
   */
  async getSecureToken(): Promise<any> {
    console.log('🎭 MOCK: Getting secure token');
    await delay(300);
    return {
      success: true,
      secureToken: `MOCK-TOKEN-${generateMockId('ST')}`,
      requestID: generateMockId('REQ'),
      proof_verifier: 'mock-proof',
      device_fingerprint: 'mock-fingerprint',
      mock: true
    };
  },

  /**
   * Mock: Onboard card (enroll + provision)
   */
  async onboardCard(data: {
    email: string;
    cardNumber: string;
    cvv: string;
    expirationMonth: string;
    expirationYear: string;
    secureToken?: string;
    browserData?: any;
  }): Promise<any> {
    console.log('🎭 MOCK: Onboarding card ending in', data.cardNumber.slice(-4));
    await delay(500);

    const vPanEnrollmentID = generateMockId('VPAN-ENR');
    const vProvisionedTokenId = generateMockId('VPROV-TOK');
    const xRequestId = generateMockId('XREQ');
    const clientReferenceId = generateMockId('CLIENT-REF');

    return {
      success: true,
      vPanEnrollmentID,
      vProvisionedTokenId,
      lastFourDigits: data.cardNumber.slice(-4),
      xRequestId,
      clientReferenceId,
      message: 'Card enrolled and token provisioned (MOCK)',
      mock: true
    };
  },

  /**
   * Mock: Device attestation (both AUTHENTICATE and REGISTER steps)
   */
  async deviceAttestation(data: {
    email: string;
    vProvisionedTokenId: string;
    secureToken: string;
    browserData?: any;
    step: 'AUTHENTICATE' | 'REGISTER';
    panData?: string;
    xRequestId?: string;
    clientReferenceId?: string;
  }): Promise<any> {
    console.log(`🎭 MOCK: Device attestation (${data.step})`);
    await delay(400);

    if (data.step === 'AUTHENTICATE') {
      return {
        success: true,
        action: 'REGISTER',
        message: 'Device attestation authenticate (MOCK)',
        mock: true
      };
    } else {
      // REGISTER
      return {
        success: true,
        authenticationContext: {
          endpoint: 'https://mock.visa.local/attestation',
          identifier: data.vProvisionedTokenId,
          payload: 'mock-webauthn-challenge',
          action: 'REGISTER'
        },
        message: 'Device attestation register (MOCK)',
        mock: true
      };
    }
  },

  /**
   * Mock: Device binding (get step-up options)
   */
  async deviceBinding(data: {
    vProvisionedTokenId: string;
    secureToken: string;
    email: string;
    browserData?: any;
    xRequestId: string;
    clientReferenceId: string;
  }): Promise<any> {
    console.log('🎭 MOCK: Device binding');
    await delay(400);

    return {
      success: true,
      stepUpRequest: [
        {
          method: 'OTPSMS',
          value: '***-***-1234',
          identifier: `SMS-${generateMockId('SMS')}`
        },
        {
          method: 'OTPEMAIL',
          value: data.email,
          identifier: `EMAIL-${generateMockId('EMAIL')}`
        }
      ],
      status: 'CHALLENGE',
      message: 'Device binding complete (MOCK)',
      mock: true
    };
  },

  /**
   * Mock: Step-up (send OTP)
   */
  async stepUp(data: {
    vProvisionedTokenId: string;
    identifier: string;
    method: string;
    xRequestId: string;
    clientReferenceId: string;
  }): Promise<any> {
    console.log(`🎭 MOCK: Sending OTP via ${data.method}`);
    await delay(300);

    return {
      success: true,
      status: 'OTP_SENT',
      message: 'OTP sent (MOCK MODE - use any code)',
      mock: true
    };
  },

  /**
   * Mock: Validate OTP
   */
  async validateOtp(data: {
    vProvisionedTokenId: string;
    otpValue: string;
    xRequestId: string;
    clientReferenceId: string;
  }): Promise<any> {
    console.log('🎭 MOCK: Validating OTP:', data.otpValue);
    await delay(300);

    // Accept any OTP in mock mode
    return {
      success: true,
      status: 'VALIDATED',
      message: 'OTP validated (MOCK MODE)',
      mock: true
    };
  },

  /**
   * Mock: Complete passkey registration
   */
  async completePasskey(data: {
    vProvisionedTokenId: string;
    fidoBlob: string;
  }): Promise<any> {
    console.log('🎭 MOCK: Completing passkey registration');
    await delay(300);

    return {
      success: true,
      code: 'mock-auth-code',
      fidoBlob: 'mock-fido-blob',
      hint: 'mock-hint',
      message: 'Passkey registration complete (MOCK)',
      mock: true
    };
  },

  /**
   * Mock: VIC enroll card
   */
  async vicEnrollCard(data: {
    email: string;
    vProvisionedTokenId: string;
  }): Promise<any> {
    console.log('🎭 MOCK: VIC enroll card');
    await delay(400);

    return {
      success: true,
      clientReferenceId: generateMockId('VIC-CLIENT-REF'),
      message: 'VIC card enrolled (MOCK)',
      mock: true
    };
  },

  /**
   * Mock: VIC initiate purchase
   */
  async vicInitiatePurchase(data: {
    vProvisionedTokenId: string;
    fidoBlob: string;
    email: string;
  }): Promise<any> {
    console.log('🎭 MOCK: VIC initiate purchase');
    await delay(400);

    return {
      success: true,
      instructionId: generateMockId('VIC-INST'),
      message: 'VIC purchase initiated (MOCK)',
      mock: true
    };
  },

  /**
   * Mock: VIC get payment credentials
   */
  async vicPaymentCredentials(data: {
    instructionId: string;
    vProvisionedTokenId: string;
  }): Promise<any> {
    console.log('🎭 MOCK: VIC payment credentials');
    await delay(400);

    return {
      success: true,
      signedPayload: {
        accountNumber: '4111111111111111',
        expirationDate: { month: '12', year: '2029' },
        cvv2: '123',
        cryptogram: 'MOCK-CRYPTOGRAM-BASE64',
        mock: true
      },
      message: 'VIC payment credentials retrieved (MOCK)',
      mock: true
    };
  }
};

export default visaMockService;
