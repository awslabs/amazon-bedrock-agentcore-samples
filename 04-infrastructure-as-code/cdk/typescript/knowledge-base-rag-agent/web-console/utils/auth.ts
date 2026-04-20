import { Amplify } from 'aws-amplify';
import { signIn as amplifySignIn, signOut as amplifySignOut, getCurrentUser as amplifyGetCurrentUser, fetchAuthSession } from 'aws-amplify/auth';

// Configure Amplify
export const configureAmplify = () => {
  const config: any = {
    Auth: {
      Cognito: {
        userPoolId: process.env.COGNITO_USER_POOL_ID,
        userPoolClientId: process.env.COGNITO_USER_POOL_WEB_CLIENT_ID,
      },
    },
  };

  // Add identityPoolId only if it exists
  if (process.env.COGNITO_IDENTITY_POOL_ID) {
    config.Auth.Cognito.identityPoolId = process.env.COGNITO_IDENTITY_POOL_ID;
  }

  Amplify.configure(config);
};

// Sign in
export const signIn = async (username: string, password: string) => {
  try {
    const { isSignedIn } = await amplifySignIn({ username, password });
    if (isSignedIn) {
      const user = await amplifyGetCurrentUser();
      return { success: true, user };
    }
    return { success: false, error: 'Sign in failed' };
  } catch (error) {
    console.error('Error signing in:', error);
    return { success: false, error };
  }
};

// Sign out
export const signOut = async () => {
  try {
    await amplifySignOut();
    return { success: true };
  } catch (error) {
    console.error('Error signing out:', error);
    return { success: false, error };
  }
};

// Get current authenticated user
export const getCurrentUser = async () => {
  try {
    const user = await amplifyGetCurrentUser();
    return { success: true, user };
  } catch (error) {
    console.error('Error getting current user:', error);
    return { success: false, error };
  }
};

// Get current session
export const getCurrentSession = async () => {
  try {
    const session = await fetchAuthSession();
    return { success: true, session };
  } catch (error) {
    console.error('Error getting current session:', error);
    return { success: false, error };
  }
};

// Get JWT token
export const getJwtToken = async () => {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() || null;
  } catch (error) {
    console.error('Error getting JWT token:', error);
    return null;
  }
};

// Check if user is authenticated
export const isAuthenticated = async () => {
  try {
    await amplifyGetCurrentUser();
    return true;
  } catch (_error) {
    return false;
  }
};
