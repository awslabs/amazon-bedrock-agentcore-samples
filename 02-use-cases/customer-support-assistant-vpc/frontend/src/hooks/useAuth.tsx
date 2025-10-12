import { useState, useEffect, createContext, useContext, ReactNode } from 'react'
import type { AuthState, TokenResponse, UserClaims, AppConfig } from '../types'
import * as authService from '../services/authService'

interface AuthContextType extends AuthState {
  login: () => void
  logout: () => void
  handleCallback: (code: string, state: string) => Promise<void>
  config: AppConfig | null
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
  stackName?: string
}

export function AuthProvider({ children, stackName = 'customer-support-vpc' }: AuthProviderProps) {
  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    tokens: null,
    userClaims: null,
    loading: true,
    error: null,
  })

  const [config, setConfig] = useState<AppConfig | null>(null)

  // Load configuration from backend API (which fetches from SSM Parameters)
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await fetch(`/api/config?stack=${stackName}`)

        if (!response.ok) {
          throw new Error(`Failed to fetch config: ${response.status}`)
        }

        const data = await response.json()

        setConfig({
          stackName: data.stackName,
          cognitoDomain: data.cognitoDomain.replace('https://', ''),
          clientId: data.clientId,
          redirectUri: window.location.origin + '/',
          scopes: 'email openid profile',
        })
      } catch (error) {
        console.error('Error loading configuration:', error)
        setAuthState((prev) => ({
          ...prev,
          error: 'Failed to load configuration from server',
          loading: false,
        }))
      }
    }

    loadConfig()
  }, [stackName])

  // Check authentication status on mount
  useEffect(() => {
    if (!config) return

    const tokens = authService.getTokens()
    if (tokens) {
      try {
        const userClaims = authService.getUserClaims(tokens.id_token)
        setAuthState({
          isAuthenticated: true,
          tokens,
          userClaims,
          loading: false,
          error: null,
        })
      } catch (error) {
        console.error('Error decoding token:', error)
        authService.clearTokens()
        setAuthState({
          isAuthenticated: false,
          tokens: null,
          userClaims: null,
          loading: false,
          error: null,
        })
      }
    } else {
      setAuthState((prev) => ({
        ...prev,
        loading: false,
      }))
    }
  }, [config])

  const login = async () => {
    if (!config) {
      console.error('Configuration not loaded')
      return
    }

    try {
      const loginUrl = await authService.getLoginURL(
        config.cognitoDomain,
        config.clientId,
        config.redirectUri,
        config.scopes
      )
      window.location.href = loginUrl
    } catch (error) {
      console.error('Error generating login URL:', error)
      setAuthState((prev) => ({
        ...prev,
        error: 'Failed to initiate login',
      }))
    }
  }

  const logout = () => {
    if (!config) return

    authService.logout()
    setAuthState({
      isAuthenticated: false,
      tokens: null,
      userClaims: null,
      loading: false,
      error: null,
    })

    const logoutUrl = authService.getLogoutURL(
      config.cognitoDomain,
      config.clientId,
      config.redirectUri
    )
    window.location.href = logoutUrl
  }

  const handleCallback = async (code: string, state: string) => {
    if (!config) {
      throw new Error('Configuration not loaded')
    }

    const { state: storedState } = authService.getPKCEValues()

    if (state !== storedState) {
      throw new Error('State mismatch - potential CSRF detected')
    }

    try {
      const tokens = await authService.exchangeCodeForTokens(
        code,
        config.cognitoDomain,
        config.clientId,
        config.redirectUri
      )

      authService.storeTokens(tokens)

      const userClaims = authService.getUserClaims(tokens.id_token)

      setAuthState({
        isAuthenticated: true,
        tokens,
        userClaims,
        loading: false,
        error: null,
      })
    } catch (error) {
      console.error('Error handling OAuth callback:', error)
      setAuthState((prev) => ({
        ...prev,
        error: 'Failed to complete authentication',
        loading: false,
      }))
      throw error
    }
  }

  return (
    <AuthContext.Provider value={{ ...authState, login, logout, handleCallback, config }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
