import { decodeJwt } from 'jose'
import type { TokenResponse, UserClaims } from '../types'
import { generatePKCEPair, generateUUID, getLocalStorage, setLocalStorage, removeLocalStorage } from '../lib/utils'

const TOKEN_STORAGE_KEY = 'auth_tokens'
const CODE_VERIFIER_KEY = 'code_verifier'
const CODE_CHALLENGE_KEY = 'code_challenge'
const OAUTH_STATE_KEY = 'oauth_state'

/**
 * Store PKCE values
 */
export async function storePKCEValues(): Promise<{ codeVerifier: string; codeChallenge: string; state: string }> {
  const { codeVerifier, codeChallenge } = await generatePKCEPair()
  const state = generateUUID()

  setLocalStorage(CODE_VERIFIER_KEY, codeVerifier)
  setLocalStorage(CODE_CHALLENGE_KEY, codeChallenge)
  setLocalStorage(OAUTH_STATE_KEY, state)

  return { codeVerifier, codeChallenge, state }
}

/**
 * Get stored PKCE values
 */
export function getPKCEValues(): { codeVerifier: string | null; state: string | null } {
  const codeVerifier = getLocalStorage<string>(CODE_VERIFIER_KEY)
  const state = getLocalStorage<string>(OAUTH_STATE_KEY)

  return { codeVerifier, state }
}

/**
 * Clear PKCE values
 */
export function clearPKCEValues(): void {
  removeLocalStorage(CODE_VERIFIER_KEY)
  removeLocalStorage(CODE_CHALLENGE_KEY)
  removeLocalStorage(OAUTH_STATE_KEY)
}

/**
 * Generate login URL
 */
export async function getLoginURL(
  cognitoDomain: string,
  clientId: string,
  redirectUri: string,
  scopes: string
): Promise<string> {
  const { codeChallenge, state } = await storePKCEValues()

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: scopes,
    code_challenge_method: 'S256',
    code_challenge: codeChallenge,
    state: state,
  })

  return `https://${cognitoDomain}/oauth2/authorize?${params.toString()}`
}

/**
 * Exchange authorization code for tokens
 */
export async function exchangeCodeForTokens(
  code: string,
  cognitoDomain: string,
  clientId: string,
  redirectUri: string
): Promise<TokenResponse> {
  const { codeVerifier } = getPKCEValues()

  if (!codeVerifier) {
    throw new Error('Code verifier not found')
  }

  const tokenUrl = `https://${cognitoDomain}/oauth2/token`

  const params = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: clientId,
    code: code,
    redirect_uri: redirectUri,
    code_verifier: codeVerifier,
  })

  try {
    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Failed to exchange code: ${response.status} - ${errorText}`)
    }

    const tokens = await response.json() as TokenResponse
    return tokens
  } catch (error) {
    console.error('Error exchanging code for tokens:', error)
    throw error
  }
}

/**
 * Store tokens in localStorage
 */
export function storeTokens(tokens: TokenResponse): void {
  setLocalStorage(TOKEN_STORAGE_KEY, tokens)
  clearPKCEValues()
}

/**
 * Get tokens from localStorage
 */
export function getTokens(): TokenResponse | null {
  return getLocalStorage<TokenResponse>(TOKEN_STORAGE_KEY)
}

/**
 * Clear tokens from localStorage
 */
export function clearTokens(): void {
  removeLocalStorage(TOKEN_STORAGE_KEY)
}

/**
 * Decode ID token to get user claims
 */
export function getUserClaims(idToken: string): UserClaims {
  return decodeJwt(idToken) as unknown as UserClaims
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  const tokens = getTokens()
  return tokens !== null && tokens.access_token !== undefined
}

/**
 * Get logout URL
 */
export function getLogoutURL(cognitoDomain: string, clientId: string, logoutUri: string): string {
  const params = new URLSearchParams({
    client_id: clientId,
    logout_uri: logoutUri,
  })

  return `https://${cognitoDomain}/logout?${params.toString()}`
}

/**
 * Logout user
 */
export function logout(): void {
  clearTokens()
  clearPKCEValues()
}
