import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { signIn as amplifySignIn, signOut as amplifySignOut, getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';
import { Hub } from 'aws-amplify/utils';
import { useRouter } from 'next/router';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: any;
  signIn: (username: string, password: string) => Promise<any>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
  error: string | null;
  isRefreshing: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [user, setUser] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const refreshAttempts = useRef(0);
  const maxRefreshAttempts = 3;
  const router = useRouter();

  const checkAuth = async () => {
    setIsLoading(true);
    try {
      const user = await getCurrentUser();
      setIsAuthenticated(true);
      setUser(user);
    } catch (_error) {
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const signIn = async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const { isSignedIn, nextStep } = await amplifySignIn({ username, password });
      if (isSignedIn) {
        const user = await getCurrentUser();
        setIsAuthenticated(true);
        setUser(user);
        return { success: true, user };
      } else {
        // Handle additional steps if needed (MFA, etc.)
        console.log('Additional sign-in steps required:', nextStep);
        return { success: false, error: 'Additional authentication steps required' };
      }
    } catch (error) {
      console.error('Error signing in:', error);
      setError(error instanceof Error ? error.message : 'An error occurred during sign in');
      return { success: false, error };
    } finally {
      setIsLoading(false);
    }
  };

  const signOut = useCallback(async () => {
    setIsLoading(true);
    try {
      await amplifySignOut();
      setIsAuthenticated(false);
      setUser(null);
      router.push('/login');
    } catch (error) {
      console.error('Error signing out:', error);
      setError(error instanceof Error ? error.message : 'An error occurred during sign out');
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  // Wrap refreshSession in useCallback to prevent stale closures
  const refreshSession = useCallback(async () => {
    // Prevent concurrent refresh attempts
    if (isRefreshing) {
      console.log('Refresh already in progress, skipping');
      return;
    }

    // Check max attempts
    if (refreshAttempts.current >= maxRefreshAttempts) {
      console.error('Max refresh attempts reached, signing out');
      await signOut();
      return;
    }

    setIsRefreshing(true);
    refreshAttempts.current += 1;

    try {
      const session = await fetchAuthSession({ forceRefresh: true });
      
      if (session.tokens) {
        console.log('Session refreshed successfully');
        refreshAttempts.current = 0; // Reset on success
      } else {
        throw new Error('No tokens in session');
      }
    } catch (error) {
      console.error('Error refreshing session:', error);
      
      // Exponential backoff before retry
      const backoffDelay = Math.min(1000 * Math.pow(2, refreshAttempts.current), 30000);
      
      if (refreshAttempts.current < maxRefreshAttempts) {
        console.log(`Retrying refresh in ${backoffDelay}ms (attempt ${refreshAttempts.current}/${maxRefreshAttempts})`);
        setTimeout(() => {
          setIsRefreshing(false);
          refreshSession();
        }, backoffDelay);
      } else {
        console.error('Max refresh attempts reached, signing out');
        await signOut();
      }
    } finally {
      if (refreshAttempts.current === 0 || refreshAttempts.current >= maxRefreshAttempts) {
        setIsRefreshing(false);
      }
    }
  }, [isRefreshing, signOut]);

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();

    // Listen for auth events
    const unsubscribe = Hub.listen('auth', ({ payload }) => {
      switch (payload.event) {
        case 'signedIn':
          setIsAuthenticated(true);
          checkAuth(); // Refresh user data
          break;
        case 'signedOut':
          setIsAuthenticated(false);
          setUser(null);
          break;
        case 'tokenRefresh':
          refreshSession();
          break;
      }
    });

    return () => unsubscribe();
  }, [refreshSession]);

  // Set up a timer to refresh the session periodically
  useEffect(() => {
    if (!isAuthenticated) return; // Early return if not authenticated

    const interval = setInterval(refreshSession, 15 * 60 * 1000); // Refresh every 15 minutes

    return () => clearInterval(interval);
  }, [isAuthenticated, refreshSession]);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        signIn,
        signOut,
        refreshSession,
        error,
        isRefreshing,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
