# Visa Intelligent Commerce Integration - Implementation Guide

## Overview

This comprehensive guide explains the complete process flow for integrating Visa’s Intelligent Commers suite which includes tokenization,  authentication, payment instruction and commerce signals  into your AI agent application. The integration enables safe and secure payments while protecting sensitive card data throughout the entire transaction lifecycle.

## Before You Begin: Understanding the Complete Integration Journey

The Visa payment integration consists of five distinct phases that work together to create a secure, seamless payment experience:

**Phase 1: Prerequisites and Onboarding** (see [Onboarding Process](#onboarding-process))

- Onboarding to Visa Intelligent Commerce platform
- Obtaining API credentials (API Key, Key ID, Client App ID)
- Setting up your technical infrastructure (HTTPS, database, FIDO2-compatible environment)

**Phase 2: Tokenization** - Enroll card number to receive secure token (one-time setup per card)

**Phase 3: Authentication - Passkey Setup** - Binding payment tokens to specific devices using FIDO2 (one-time setup per device)

**Phase 4: Purchase Intent** - Capture consumers instruction and intent for transacting

**Phase 5: Complete Purchase** - Generating and using secure payment credentials / cryptograms

This guide focuses on Phases 2-5, which detail the technical implementation of the payment flow itself. Before proceeding with these phases, ensure you have completed Phase 1 by onboarding to Visa Intelligent Commerce and obtaining all necessary credentials as described in the Prerequisites and Requirements section above.

The diagrams throughout this guide reference these phase numbers to help you understand where each step fits in the overall integration journey.

## Understanding the Architecture

### Agent Framework Options

Your payment agent serves as an intelligent intermediary between users and merchants, orchestrating the entire payment flow while maintaining security and user experience. You have two primary architectural approaches for building this agent:

**AWS AgentCore Framework**: This is Amazon's purpose-built framework for creating AI agents with sophisticated orchestration capabilities. AgentCore provides built-in state management, conversation handling, and integration patterns that make it ideal for complex, multi-step payment flows. It handles the complexity of managing user sessions, coordinating between multiple services, and maintaining context across interactions.

**Model Context Protocol (MCP) Server**: MCP offers a standardized approach to agent-to-service communication. It defines clear protocols for how your agent communicates with external services like Visa's payment platform. MCP servers can be deployed independently and provide a clean separation between your agent logic and service integrations.

> **Important Note**: A separate, detailed architecture guide covers the specific implementation patterns, configuration requirements, and best practices for both AWS AgentCore and MCP Server deployments. This guide focuses on the payment integration flow itself.

### The Visa Payment Platform

Your agent integrates with three distinct but interconnected Visa services, each serving a specific purpose in the payment ecosystem:

**Visa Token Service (VTS)**: This kicks off the start of the workflow to initiate the ability to make payments. VTS handles the critical process of providing a corresponding secure token ID based on the actual card numbers (PANs) provided. It also manages device binding, which creates a cryptographic link between a payment token and a specific user device. This binding ensures that even if a token is compromised, it cannot be used from an unauthorized device. VTS also handles the step-up authentication flows, including OTP verification, that establish identify of the consumer linked to the payment credential as well as trust before allowing passkey creation.

**Visa Intelligent Commerce (VIC)**: VIC orchestrates the actual payment transaction. It manages purchase instructions, which are essentially pre-authorized payment intents that prove a user has verified their identity and has consented to a specific transaction or set of transactions. VIC generates the cryptograms - payment credentials that agents utilize at merchant endpoints to process transactions.

**Visa Auth iFrame**: This is the user-facing component that provides the secure interface for passkey operations. The iFrame runs in an isolated security context, ensuring that your application never has direct access to the passkey creation or authentication process. It handles all the complex FIDO2 protocol interactions with the user's device, manages the secure display of authentication prompts, and returns only the necessary authentication proofs to your application.

## Prerequisites and Requirements

### Onboarding to Visa Intelligent Commerce

Before implementing the Visa Payment Integration, you must first onboard your AI agent to the Visa Intelligent Commerce platform. This onboarding process grants you access to the integrated services required for secure, agent-based payment processing.

### Understanding Visa Intelligent Commerce

Visa Intelligent Commerce is a comprehensive platform that enables safe, secure, and personalized AI commerce at scale. The platform provides five integrated services that work together to facilitate agent-based transactions:

- **Tokenization**: Agent-specific payment tokens for use at Visa-accepting merchant locations
- **Authentication**: Step-up verification and Passkey setup for secure cardholder authentication
- **Payment Instructions**: Controls to ensure payment requests match authenticated user instructions
- **Signals**: Commerce signals for dispute resolution and transaction tracking
- **Personalization**: User insights for enhanced, personalized experiences (with user consent)

### Onboarding Process

To begin integration, you must complete the agent onboarding process through Visa's Developer Portal at [developer.visa.com](https://developer.visa.com). To receive access email GDLAICommerceSupport@visa.com.

You can also directly message [here..](https://globalclient.visa.com/AI-Commerce)

During onboarding, you will:

**Register Your Application**: Create a project on the Visa Developer Platform and register your AI agent application

**Obtain Required Credentials**: Receive the following authentication credentials:
- **API Key**: Primary authentication credential for VTS and VIC API calls (separate keys for sandbox and production)
- **Key ID**: Identifier for VIC operations involving encrypted payloads
- **Client App ID**: Your registered application identifier within Visa's ecosystem (e.g., "VICTestAccountTR" for testing)

**Access API Documentation**: Gain access to comprehensive technical documentation including:
Access API Documentation: Gain access to comprehensive technical documentation including: 
Visa Intelligent Commerce – [API Documentation](https://developer.visa.com/capabilities/visa-intelligent-commerce/docs-getting-started)
[Visa Intelligent Commerce – MCP](https://github.com/visa/mcp)

### Regional Availability

Visa Intelligent Commerce is available in the following regions:
- North America
- Asia-Pacific
- Europe
- CEMEA (Central Europe, Middle East, and Africa)
- LAC (Latin America and Caribbean)

### Fees and Terms

The platform is free to use in the Sandbox environment for development and testing. For production deployment, contact Visa directly to discuss pricing and terms. 

### Technical Requirements

Once onboarded, your implementation must meet the following technical requirements:

**HTTPS-Enabled Web Application**: All communication with Visa services requires valid SSL/TLS certificates from a trusted certificate authority

**Database Infrastructure**: Persistent storage for user profiles, payment tokens, passkey data, and transaction history

**FIDO2-Compatible Browser**: Modern browsers (Chrome 67+, Safari 14+, Edge 18+) with access to secure authenticators (Touch ID, Windows Hello, or hardware security keys)

### Getting Started

1. Visit [developer.visa.com/capabilities/visa-intelligent-commerce](https://developer.visa.com/capabilities/visa-intelligent-commerce)
2. Click "Start Project" to begin the onboarding process
3. Review the API documentation for each integrated service
4. Work with your Visa account team to obtain sandbox credentials for development and testing
5. Follow this implementation guide to integrate the payment flow into your AI agent


## Phase 2: Card Tokenization - The Foundation of Secure Payments

Card tokenization is a one-time setup process that transforms a user's actual card number into a secure token that can be safely stored and reused. This phase happens when a user first adds a payment method to your agent.

### Step 1: PAN Enrollment - Initiating the Tokenization Process

The enrollment process begins when your user provides their card details. This is the only time you'll handle the actual card number, and even then, it should be encrypted immediately.

**The User Experience**: Your application presents a secure form where the user enters their card number (PAN), CVV2 security code, expiration date, and billing address. This form should clearly communicate that this is a one-time setup and that the card will be securely tokenized.

**The Technical Process**: Once collected, the card data must be encrypted using Visa's JWE (JSON Web Encryption) format. This encryption happens client-side before the data ever reaches your servers. The encrypted payload is then sent to VTS's PAN enrollment endpoint. VTS decrypts the data in its secure environment, validates the card details, and creates an enrollment session.

**What You Receive**: VTS responds with a `vPanEnrollmentID`. This is a temporary identifier that represents this specific enrollment session. It's not the final token - think of it as a session ID that proves you've successfully initiated the enrollment process. You also receive basic card metadata like the last 4 digits and expiration date, which you can display to the user for confirmation.

**Temporary Storage**: The enrollment ID should be kept in memory or a short-lived session store. You'll need it for the next step, but it's not meant for long-term storage. It typically expires within a few minutes if not used.

### Step 2: Token Provisioning - Creating the Permanent Payment Token

With the enrollment ID in hand, you now request the actual payment token that will be used for all future transactions.

**The Provisioning Request**: You send the enrollment ID back to VTS along with additional context about the device and risk profile. This includes information about the user's device (type, model, operating system), the IP address, and risk indicators. You also specify the presentation type as "AI_AGENT" to indicate this token will be used in an agent-based commerce scenario.

**VTS Processing**: VTS takes the enrollment ID, retrieves the associated card data from its secure storage, and generates a unique token. This token is cryptographically linked to the original card but cannot be reverse-engineered to reveal the card number. VTS also creates a token reference ID for tracking and associates the token with your application.

**What You Receive**: The response contains several critical pieces of information. The `vProvisionedTokenID` is your primary payment identifier - this is what you'll use in all future payment operations. The `tokenReferenceID` provides an additional reference for tracking and reconciliation. You also receive token metadata including the last 4 digits (for displaying to users), expiration date, and optionally, card art URLs that you can use in your UI to show the card brand and design.

**Permanent Storage**: This is the data you store in your database, linked to the user's profile. The token ID becomes the primary key for all payment operations. The last 4 digits help users identify which card they're using. The expiration date lets you know when the token will need to be renewed.

**Critical Security Point**: Notice that at no point does your database ever contain the actual card number or CVV2. You only store the token ID and display metadata. Even if your database is completely compromised, attackers cannot use this information to make fraudulent purchases because they don't have the passkey authentication data (which comes in Phase 3) and they can't generate valid cryptograms without going through VIC.


## Phase 3: Passkey Setup - Binding Payment to Device

Passkey setup creates a cryptographic binding between the payment token and the user's specific device using the FIDO2 standard. Like tokenization, this is a one-time setup process.

### Step 3: Initializing a Secure Session

Every passkey operation begins with establishing a secure session with Visa's Auth iFrame.

**The Two-Step Handshake**: The iFrame initialization is a two-step process. First, you make a GET request to the Auth iFrame endpoint with your API key and client app ID. This returns a request ID and confirms the iFrame is ready. Second, you POST to the same endpoint with the request ID and a command to create an authentication session. This two-step process ensures that the session is properly initialized and prevents certain types of replay attacks.

**What You Receive**: The response contains several important elements. The `secureToken` is an encrypted session token that will be used in subsequent VTS API calls to prove that you have an active, authenticated session with the iFrame. The `dfpSessionID` is a device fingerprint session identifier used for fraud detection. The `requestID` ties all subsequent iFrame operations to this specific session.

**Session Lifecycle**: This secure token is valid only for the current operation (either passkey creation or authentication). Once used, it expires. This means every transaction requires a fresh session, which might seem inefficient but is crucial for security - it prevents token reuse attacks and ensures that each operation is independently authenticated.

**Memory vs. Persistence**: The secure token should be kept in memory during the operation but never persisted to your database. It's ephemeral by design. If the user abandons the flow and comes back later, you'll need to create a new session.

### Step 4: Checking Device Registration Status

Before you can create a passkey, you need to know if this device has already been bound to this payment token.

**The Attestation Request**: You send a device attestation request to VTS. This request includes the secure token from Step 3, comprehensive browser data (timezone, screen dimensions, user agent, color depth, JavaScript capabilities), and transaction context (amount, merchant information, currency). The browser data helps VTS build a device fingerprint for fraud detection. The transaction context is included even though you're not making a purchase yet - it helps VTS understand the risk profile of the intended use.

**Understanding the Response**: VTS responds with an `action` field that tells you what to do next. If the action is "REGISTER", it means this device hasn't been bound to this token yet, and you need to proceed with the full device binding flow (Steps 5-9). If the action is "AUTHENTICATE", it means the device is already bound, and you can skip directly to authentication (used in Phase 4 for actual purchases).

**The Identifier**: The response also includes an `identifier` that represents this specific device/token combination. This identifier will be used throughout the remaining steps to maintain continuity.

**Why This Check Matters**: This check prevents unnecessary device binding attempts. If a user has already set up their passkey on this device, they don't need to go through OTP verification again. This improves user experience while maintaining security.


### Steps 5-7: OTP Verification - Proving User Identity

When the device needs to be bound (action was "REGISTER"), VTS requires step-up authentication to prove the user is who they claim to be. This is done through OTP (One-Time Password) verification.

**Step 5: Initiating Device Binding**

You send a device binding request to VTS, including the same secure token and browser data from Step 4. You also specify the intent as "FIDO" to indicate you're preparing for FIDO2 passkey creation.

VTS responds with available step-up methods. Typically, this includes SMS and email options. Each method comes with an identifier that you'll use to select it, and a masked value showing where the OTP will be sent (like "**PSMS" for a phone number ending in SMS, or just "OTPEMAIL" for email). The response also includes a status of "CHALLENGE", indicating that user verification is required.

**Why Multiple Methods**: Offering both SMS and email gives users flexibility. Some users might not have their phone handy, or they might prefer email for security reasons. Some regions have better SMS delivery than others. Providing options improves the user experience and completion rates.

**Step 6: Selecting the OTP Method**

The user chooses their preferred method (SMS or email), and you send a PUT request to VTS with the selected method's identifier. This tells VTS to generate an OTP and send it to the user through the chosen channel.

VTS responds with important constraints: `maxOTPRequestsAllowed` (typically 3) tells you how many times the user can request a new OTP, `maxOTPVerificationAllowed` (also typically 3) tells you how many attempts they have to enter the correct code, and `codeExpiration` (typically 5 minutes) tells you how long the OTP remains valid.

**User Experience Considerations**: Your UI should clearly show where the OTP was sent and how long it's valid. You should also implement a countdown timer and allow users to request a new code if needed (within the allowed limits). Make sure to handle the case where SMS delivery is delayed - give users the option to try email instead.

**Step 7: Validating the OTP**

The user receives the OTP (a 6-digit code) and enters it into your application. You send this code to VTS for validation, along with the same client reference ID you've been using throughout this flow to maintain continuity.

If the OTP is correct, VTS responds with an empty object (just `{}`), which indicates success. If it's incorrect, you'll receive an error response, and the user can try again (up to the maximum attempts).

**Sandbox Testing**: In Visa's sandbox environment, you can use a "golden OTP" value of `456789` that always works, bypassing the need for actual SMS/email delivery.

### Step 8: Preparing for Passkey Creation

With the user's identity verified through OTP, you're now ready to prepare for the actual passkey creation.

**The Second Attestation Request**: You send another device attestation request to VTS, but this time with a different reason code: "DEVICE_BINDING" instead of "PAYMENT". You also change the type to "REGISTER". This tells VTS that you've completed the step-up authentication and are ready to bind the device.

**The FIDO2 Challenge**: VTS generates a FIDO2 challenge and packages it into a JWT (JSON Web Token) payload. This payload contains all the information needed for the browser to create a passkey: the relying party information (Visa's domain), the challenge itself (a random value that must be signed), user information, and various FIDO2 parameters.

**What You Receive**: The response includes three critical pieces: an `endpoint` (the specific iFrame URL to use for passkey creation), an `identifier` (the device identifier), and the `payload` (the JWT containing the FIDO2 challenge). These three pieces work together - the endpoint knows how to process the payload, and the identifier ties everything back to this specific device binding session.

**Keeping It in Memory**: Like the secure token, these values should be kept in memory only for the duration of the passkey creation process. They're single-use and expire quickly.


### Step 9: Creating the Passkey Through the iFrame

**The Process**: You POST to the Auth iFrame with the endpoint, identifier, and payload from Step 8. The iFrame handles the FIDO2 passkey creation ceremony and displays the passkey creation UI to the user.

**The Response**: The iFrame returns `result: "COMPLETE"` with `assuranceData` containing the `fidoBlob` (encrypted passkey data), `rpID` (Visa's domain), and device `identifier`.

**What to Store in Your Database**: Store the `fidoBlob` (encrypted at rest), device identifier, and creation timestamp, all linked to the user profile and token ID.


## Phase 4: Purchase Intent - Authenticating for a Transaction

Now we move from one-time setup to per-transaction operations. Every time the user wants to make a purchase, they go through this phase to authenticate and create a purchase intent.

### The Difference Between Setup and Transaction

It's important to understand that Phases 2 and 3 happen once per card per device. Phase 4 happens every time the user makes a purchase. Because the device is already bound and the passkey already exists, this phase is much faster and simpler than the setup process.

### Step 10: Initializing a New Transaction Session

Even though the device is already bound, each transaction requires its own secure session.

**Why a New Session**: Security best practices dictate that session tokens should be short-lived and single-use. This prevents replay attacks where an attacker intercepts a session token and tries to reuse it. By requiring a fresh session for each transaction, the system ensures that even if a session token is compromised, it's useless after the transaction completes.

**The Process**: This is identical to Step 3 - you make the same two-step handshake with the Auth iFrame to get a new `secureToken`, `requestID`, and `dfpSessionID`. The difference is in how you'll use this session - instead of creating a passkey, you'll be authenticating with an existing one.

**Session Context**: The new session is completely independent of the setup session from Phase 3. It has its own token, its own expiration, and its own security context. This isolation is intentional and important for security.

### Step 11: Requesting Authentication

With your fresh session token, you now tell VTS that you want to authenticate for a payment.

**The Attestation Request**: This looks very similar to Step 4, but with one crucial difference - the device is already bound. You send the same type of device attestation request with browser data and transaction context (the actual amount and merchant for this purchase). You use the same reason code "PAYMENT" and type "AUTHENTICATE".

**The Different Response**: Because VTS recognizes this device (it has the device identifier from the binding process), it responds with `action: "AUTHENTICATE"` instead of "REGISTER". This tells you that you can proceed directly to passkey verification without going through OTP verification again.

**Transaction Context**: Include the transaction details (amount, merchant, currency) in this request. VTS uses this information for the authentication challenge.

**The Authentication Payload**: Along with the action, VTS returns an `endpoint`, `identifier`, and `payload` - just like in Step 8, but this time the payload contains a FIDO2 authentication challenge instead of a registration challenge. The challenge is unique to this transaction and includes the transaction details, making it impossible to reuse for a different purchase.

### Step 12: Verifying the Passkey Through the iFrame

This is where the user proves they're authorized to make this purchase by authenticating with their passkey.

**Sending the Challenge**: You POST to the Auth iFrame with the authentication endpoint, identifier, and payload from Step 11. The iFrame recognizes this as an authentication request (not a registration request) and prepares to verify the existing passkey.

**The User Interaction**: The iFrame displays pop-up windows where the user verifies their PAN and enters their passkey PIN.

**The Response**: The iFrame returns `assuranceData` and `fidoBlob` in a JWT base64 encoded string. You also get the device identifier confirming which device was used.


### Step 13: Creating the Purchase Instruction

With the user authenticated, you now create a formal purchase instruction with VIC. This instruction is like a pre-authorization that proves the user has verified their identity and has consented to these specific purchase terms and intends to make this specific purchase.

**The Purchase Instruction Request**: You send a comprehensive request to VIC that includes multiple pieces of information. The `tokenId` (from Phase 2) identifies which payment method to use. The `assuranceData` (containing the `fidoBlob` from Step 12) proves the user authenticated. The `mandates` section describes the purchase - amount, currency, merchant category, description, and constraints like decline thresholds. The `appInstance` section provides device information for fraud detection. The `consumerPrompt` can include a summary of what the user is purchasing, which can be useful for dispute resolution.

**Understanding Mandates**: The mandate structure is powerful and flexible. You can set a `declineThreshold` that specifies the maximum amount that can be charged. You can set `effectiveUntilTime` to limit how long the instruction is valid. You can specify `quantity` to allow multiple uses of the same instruction (though typically this is 1 for single purchases). The `merchantCategoryCode` helps with categorization and fraud detection.

**Device and Risk Information**: The `appInstance` section includes detailed device information - country code, device ID, IP address, device model and type, user agent, and your application name. This information is crucial for VIC's fraud detection systems. Unusual patterns (like a device suddenly appearing in a different country) can trigger additional verification.

**The Instruction ID**: VIC processes all this information, validates the authentication, checks the token status, and creates a purchase instruction. It responds with an `instructionId` - a unique identifier for this specific purchase intent. This ID is your authorization to proceed with getting payment credentials.

**What the Instruction Represents**: Think of the instruction ID as a ticket that says "this user has been authenticated, they intend to purchase X amount from Y merchant, and they're authorized to do so." It's not the actual payment yet - it's the authorization to create a payment.

**Temporary Storage**: The instruction ID should be kept in memory for the duration of the transaction. You might also want to log it for audit purposes, but it's not something you need to persist long-term. Once the transaction completes (or fails), the instruction ID is no longer useful.

**Expiration**: Purchase instructions have a limited lifetime, typically a few minutes. If you don't use the instruction ID to get payment credentials within this window, it expires and you'll need to start over with a new authentication. This prevents attackers from stealing instruction IDs and using them later.


## Phase 5: Complete Purchase - Generating and Using the Cryptogram

This is the final phase where the actual payment credential is generated and used to complete the purchase. This is where all the security measures from previous phases come together to create a secure, one-time-use payment credential.

### Step 14: Requesting the Payment Cryptogram

With your instruction ID in hand, you now request the actual payment credentials from VIC.

**The Credentials Request**: You send a request to VIC that includes the `tokenId` (identifying the payment method), the `instructionId` (proving authorization), and detailed `transactionData` (merchant country, amount, currency, merchant URL and name, and a transaction reference ID). The transaction reference ID is typically the same as the instruction ID, creating a clear audit trail.

**The Response**: VIC returns the cryptogram packaged in a JWT (JSON Web Token) called the `signedPayload`. The response also includes a status of "COMPLETED" indicating the instruction has been fulfilled.

**Decoding the JWT**: You can decode the signed payload using any JWT library. Inside, you'll find a `dynamicData` array containing the payment information. The `paymentToken` is the cryptogram. The `dynamicDataValue` is a dynamic CVV2. The `tokenExpirationMonth` and `tokenExpirationYear` indicate token expiration. The `dynamicDataExpiration` is a Unix timestamp.

### Step 15: Sending the Payment to the Merchant

Now you have a cryptogram, and you're ready to complete the purchase with the merchant.

**Extracting the Payment Data**: From the decoded JWT, you extract the `paymentToken` (cryptogram), `dynamicDataValue` (dynamic CVV2), and expiration date. You also have the transaction amount and currency from your own records.

**The Merchant's Perspective**: From the merchant's point of view, this looks like a normal card payment. They receive what appears to be a card number (the cryptogram), a CVV2 (the dynamic value), an expiration date, and the transaction amount. They process it through their normal payment gateway, just like any other card transaction.

**What the Merchant Doesn't Know**: The merchant never sees the user's actual card number. They don't know this is a tokenized payment. They don't know about the passkey authentication that happened. From their perspective, it's just a card payment. This is intentional - it means merchants don't need to change their systems to support this secure payment method.

**The Authorization Flow**: When the merchant submits the cryptogram to their payment processor, it eventually reaches Visa's authorization systems. Visa recognizes the cryptogram, validates it against the original transaction details, checks that it hasn't been used before, and verifies it hasn't expired. If everything checks out, Visa authorizes the transaction and the merchant receives approval.

**Handling Declines**: If the transaction is declined (insufficient funds, expired token, invalid cryptogram, etc.), you'll receive an error from the merchant. You should present this to the user in a clear way and give them options - try a different payment method, update their card information, or contact their bank.

### Step 16: Confirming the Transaction

After the merchant confirms the payment was successful, you send a final confirmation to VIC.

**The Confirmation Request**: You send a request to VIC with the `instructionId` and confirmation data indicating the order status is "COMPLETE".

**The Response**: VIC responds with an acknowledgment containing your client reference ID.

**What to Store**: In your database, you should store a complete transaction record. Include the instruction ID (for reference), the transaction amount and currency, the merchant name, the transaction status ("COMPLETED"), and timestamps for when the transaction was created and completed. Link this record to the user profile and the token ID. This creates a complete audit trail and provides the user with transaction history.

**Transaction Lifecycle Complete**: With the confirmation sent, the transaction is complete. The user has successfully made a purchase using tokenized payment credentials and passkey authentication, without ever exposing their actual card number to your systems or the merchant.


## Data Storage Considerations

Based on the API flow, certain data needs to be persisted to enable the payment functionality. How you structure and store this data depends on your specific business requirements and architecture.

### Core Data Elements

**User Identification**: You'll need a way to associate payment tokens and passkeys with specific users in your system.

**Payment Token Data**: The `vProvisionedTokenID` from Step 2 is required for all subsequent payment operations. You may also want to store the `tokenReferenceID` and display information like the last 4 digits and expiration date.

**Passkey Authentication Data**: The `fidoBlob` and device `identifier` from Step 9 are needed for future authentication flows. Consider encrypting the `fidoBlob` at rest.

**Transaction Records**: Depending on your business needs, you may want to store transaction history including instruction IDs, amounts, and status.


## Security Best Practices

When implementing this payment integration, consider the following security practices:

**Data Encryption**: Card data should be encrypted using Visa's JWE format. Consider encrypting sensitive data like the `fidoBlob` at rest.

**Session Management**: The `secureToken` from the Auth iFrame and `instructionId` from VIC are designed to be short-lived and single-use.

**HTTPS**: All communication with Visa's services requires HTTPS.

**Logging**: Avoid logging sensitive payment data. Use token IDs and last 4 digits for reference when needed.

Note: When deploying on AWS, security is a shared responsibility between AWS and your application.

## Next Steps for Implementation

### Review Visa's Technical Documentation

This guide provides the conceptual framework and process flow. For actual implementation, you'll need Visa's detailed API documentation, which includes exact request/response schemas, error codes and their meanings, encryption requirements and key management, and rate limits and throttling policies.

### Set Up Your Development Environment

Obtain sandbox credentials from Visa for testing. Configure HTTPS for your application with a valid SSL certificate. Set up your database schema to support user profiles, tokens, passkeys, and transactions. Implement encryption utilities for protecting sensitive data at rest.

### Build Incrementally

Start with Phase 2 (tokenization) and verify you can successfully enroll cards and provision tokens. Then add Phase 3 (passkey setup) and test the complete device binding flow including OTP verification. Finally, implement Phases 4-5 (transaction flow) and test end-to-end purchases. Test thoroughly in sandbox before moving to production.

### Refer to the Architecture Guide

For details on implementing your agent using AWS AgentCore or MCP Server, refer to the separate architecture guide. That document covers agent orchestration patterns, state management, error recovery, and deployment considerations.

## Support and Resources

- **Visa Developer Portal**: [developer.visa.com](https://developer.visa.com)
- **VTS Documentation**: [developer.visa.com/capabilities/vts](https://developer.visa.com/capabilities/vts)
- **VIC Documentation**: [developer.visa.com/capabilities/vic](https://developer.visa.com/capabilities/vic)
- **FIDO2 Specification**: [fidoalliance.org/specifications](https://fidoalliance.org/specifications/)
- **AWS AgentCore**: See separate architecture guide

