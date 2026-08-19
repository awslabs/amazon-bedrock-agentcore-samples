import { fetchUserAttributes } from 'aws-amplify/auth'

export interface CognitoUserInfo {
  userId: string
  email?: string
  givenName?: string
  familyName?: string
  fullName?: string
}

/**
 * Fetch user attributes from Cognito and format them
 */
export const getCognitoUserInfo = async (userId: string): Promise<CognitoUserInfo> => {
  try {
    const attributes = await fetchUserAttributes()

    // DEBUG: Log all attributes to see what we're getting
    console.log('🔍 DEBUG: Cognito attributes:', attributes)
    console.log('🔍 DEBUG: given_name:', attributes.given_name)
    console.log('🔍 DEBUG: family_name:', attributes.family_name)
    console.log('🔍 DEBUG: email:', attributes.email)

    const givenName = attributes.given_name
    const familyName = attributes.family_name
    const email = attributes.email

    // Create full name from given and family names
    let fullName = ''
    if (givenName && familyName) {
      fullName = `${givenName} ${familyName}`
    } else if (givenName) {
      fullName = givenName
    } else if (familyName) {
      fullName = familyName
    }

    console.log('🔍 DEBUG: Final fullName:', fullName)

    return {
      userId,
      email,
      givenName,
      familyName,
      fullName,
    }
  } catch (error) {
    console.error('Error fetching user attributes:', error)
    return {
      userId,
    }
  }
}

/**
 * Get display name for the user - prioritizes full name, falls back to email or userId
 */
export const getDisplayName = (userInfo: CognitoUserInfo): string => {
  console.log('🔍 DEBUG: getDisplayName input:', userInfo)

  if (userInfo.fullName) {
    console.log('🔍 DEBUG: Returning fullName:', userInfo.fullName)
    return userInfo.fullName
  }

  if (userInfo.givenName) {
    console.log('🔍 DEBUG: Returning givenName:', userInfo.givenName)
    return userInfo.givenName
  }

  if (userInfo.email) {
    const emailPrefix = userInfo.email.split('@')[0]
    console.log('🔍 DEBUG: Returning email prefix:', emailPrefix)
    return emailPrefix // Use email prefix as fallback
  }

  console.log('🔍 DEBUG: Returning userId (last resort):', userInfo.userId)
  return userInfo.userId // Last resort
}
