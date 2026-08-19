import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>({
  authMode: 'userPool'
})

export interface UserPreferences {
  travel: {
    budget_range: string
    interests: string[]
    accommodation_type: string
    travel_style: string
  }
  shopping: {
    categories: string[]
    price_range: string
    sustainable_preference: boolean
  }
  communication: {
    notifications: boolean
    email_updates: boolean
    language: string
  }
}

export interface PaymentCard {
  vProvisionedTokenId: string
  lastFour: string
  type: string
  expirationDate: string
  isPrimary?: boolean
  addedAt: string
}

export interface UserProfileData {
  id?: string
  userId: string
  name?: string
  email?: string
  address?: string
  notes?: string
  onboardingCompleted: boolean
  preferences?: UserPreferences
  paymentCards?: PaymentCard[]
  createdAt?: string
  updatedAt?: string
}

/**
 * User Profile Service using AppSync GraphQL
 */
export const userProfileService = {
  /**
   * Create a new user profile
   */
  async createUserProfile(
    email: string,
    name: string,
    preferences: UserPreferences,
    userId?: string,
    _address?: string
  ): Promise<UserProfileData> {
    // Verify user is authenticated
    try {
      const { getCurrentUser } = await import('aws-amplify/auth')
      await getCurrentUser()
    } catch {
      throw new Error('User not authenticated. Please sign in again.')
    }

    const response = await client.models.UserProfile.create({
      userId: userId || 'current-user',
      name,
      email,
      onboardingCompleted: true,
      preferences: JSON.stringify(preferences)
    })

    if (response.errors && response.errors.length > 0) {
      throw new Error(`Failed to create user profile: ${response.errors[0].message}`)
    }

    const profile = response.data as any

    return {
      id: profile?.id,
      userId: profile?.userId || userId || 'current-user',
      name: profile?.name || name,
      email: profile?.email || email,
      onboardingCompleted: profile?.onboardingCompleted || true,
      preferences: profile?.preferences ? JSON.parse(profile.preferences) : preferences,
      createdAt: profile?.createdAt,
      updatedAt: profile?.updatedAt
    }
  },

  /**
   * Get user profile by user ID
   */
  async getUserProfile(userId: string): Promise<UserProfileData | null> {
    const response = await client.models.UserProfile.list({
      filter: {
        userId: { eq: userId }
      }
    })

    if (response.errors && response.errors.length > 0) {
      throw new Error(`Failed to get user profile: ${response.errors[0].message}`)
    }

    const profiles = response.data || []
    if (profiles.length === 0) {
      return null
    }

    const profile = profiles[0]
    
    // Debug: log raw preferences from DynamoDB
    console.log('🔍 Raw profile.preferences type:', typeof profile.preferences)
    console.log('🔍 Raw profile.preferences:', profile.preferences)

    // Handle preferences - could be string (needs parsing) or already an object
    let parsedPreferences = undefined
    if (profile.preferences) {
      if (typeof profile.preferences === 'string') {
        parsedPreferences = JSON.parse(profile.preferences)
      } else {
        parsedPreferences = profile.preferences
      }
    }
    console.log('🔍 Parsed preferences:', parsedPreferences)

    return {
      id: profile.id,
      userId: profile.userId,
      name: profile.name || undefined,
      email: profile.email || undefined,
      address: profile.address || undefined,
      notes: profile.notes || undefined,
      onboardingCompleted: profile.onboardingCompleted || false,
      preferences: parsedPreferences,
      createdAt: profile.createdAt || undefined,
      updatedAt: profile.updatedAt || undefined
    }
  },

  /**
   * Update user profile
   */
  async updateUserProfile(
    userId: string,
    updates: Partial<Omit<UserProfileData, 'id' | 'userId' | 'createdAt' | 'updatedAt'>>
  ): Promise<UserProfileData> {
    const existingProfile = await this.getUserProfile(userId)
    if (!existingProfile || !existingProfile.id) {
      throw new Error('Profile not found for update')
    }

    const updateData: any = {}
    if (updates.name !== undefined) updateData.name = updates.name
    if (updates.email !== undefined) updateData.email = updates.email
    if (updates.address !== undefined) updateData.address = updates.address
    if ((updates as any).notes !== undefined) updateData.notes = (updates as any).notes
    if (updates.onboardingCompleted !== undefined) updateData.onboardingCompleted = updates.onboardingCompleted
    if (updates.preferences !== undefined) updateData.preferences = JSON.stringify(updates.preferences)

    const response = await client.models.UserProfile.update({
      id: existingProfile.id,
      ...updateData
    })

    if (response.errors && response.errors.length > 0) {
      throw new Error(`Failed to update user profile: ${response.errors[0].message}`)
    }

    const profile = response.data as any

    return {
      id: profile?.id,
      userId: profile?.userId || userId,
      name: profile?.name || undefined,
      email: profile?.email || undefined,
      address: profile?.address || undefined,
      notes: profile?.notes || undefined,
      onboardingCompleted: profile?.onboardingCompleted || false,
      preferences: profile?.preferences ? JSON.parse(profile.preferences) : undefined,
      createdAt: profile?.createdAt,
      updatedAt: profile?.updatedAt
    }
  },

  /**
   * Add payment card to user profile with VIC session IDs for purchase flow
   */
  async addPaymentCard(
    userId: string,
    cardData: {
      vProvisionedTokenId: string
      lastFour: string
      type: string
      expirationDate: string
      cardholderName?: string
      isPrimary?: boolean
      // VIC session IDs for purchase flow
      consumerId?: string
      clientDeviceId?: string
      clientReferenceId?: string
    }
  ): Promise<UserProfileData> {
    console.log('🔵 addPaymentCard called for userId:', userId)
    console.log('🔵 Card data:', JSON.stringify(cardData, null, 2))
    
    const existingProfile = await this.getUserProfile(userId)
    if (!existingProfile) {
      throw new Error('Profile not found. Please create profile first.')
    }
    console.log('🔵 Existing profile found, id:', existingProfile.id)

    const preferences = existingProfile.preferences || {
      travel: { budget_range: '', interests: [], accommodation_type: '', travel_style: '' },
      shopping: { categories: [], price_range: '', sustainable_preference: false },
      communication: { notifications: true, email_updates: true, language: 'en' }
    }

    if (!(preferences as any).payment) {
      (preferences as any).payment = {}
    }

    // Parse expiration date for storage
    const [month, year] = cardData.expirationDate.split('/')

    // Create card object with all data including VIC session IDs
    const cardInfo = {
      vProvisionedTokenId: cardData.vProvisionedTokenId,
      type: cardData.type,
      cardNumber: cardData.lastFour,
      lastFour: cardData.lastFour,
      expirationDate: cardData.expirationDate,
      expiryMonth: month,
      expiryYear: year,
      cardholderName: cardData.cardholderName || '',
      cvv: '***',
      // VIC session IDs needed for purchase flow
      consumerId: cardData.consumerId,
      clientDeviceId: cardData.clientDeviceId,
      clientReferenceId: cardData.clientReferenceId,
      enrolledAt: new Date().toISOString()
    }

    // Store in primaryCard or backupCard based on isPrimary flag
    if (cardData.isPrimary !== false) {
      (preferences as any).payment.primaryCard = cardInfo
      console.log('🔵 Setting primaryCard:', JSON.stringify(cardInfo, null, 2))
    } else {
      (preferences as any).payment.backupCard = cardInfo
      console.log('🔵 Setting backupCard:', JSON.stringify(cardInfo, null, 2))
    }

    console.log('🔵 Full preferences to save:', JSON.stringify(preferences, null, 2))

    const result = await this.updateUserProfile(userId, { preferences })
    console.log('🔵 Profile updated successfully')
    return result
  },

  /**
   * Get enrolled card with VIC session IDs (uses primaryCard)
   */
  async getEnrolledCard(userId: string): Promise<{
    vProvisionedTokenId: string
    consumerId: string
    clientDeviceId: string
    clientReferenceId: string
    lastFour: string
    type: string
    expirationDate: string
  } | null> {
    console.log('🔍 getEnrolledCard called for userId:', userId)
    const profile = await this.getUserProfile(userId)
    console.log('🔍 Profile found:', !!profile)
    console.log('🔍 Profile preferences:', profile?.preferences ? 'exists' : 'null')
    if (!profile?.preferences) return null

    const payment = (profile.preferences as any).payment
    console.log('🔍 Payment object:', payment ? 'exists' : 'null')

    // Get primaryCard (which now contains all VIC session data)
    const primaryCard = payment?.primaryCard
    console.log('🔍 Primary card:', primaryCard ? JSON.stringify(primaryCard) : 'null')

    if (!primaryCard) return null

    // CRITICAL: Check if card has actual data (not just empty placeholder)
    // A valid card must have vProvisionedTokenId OR at least lastFour/cardNumber and type
    const hasTokenId = primaryCard.vProvisionedTokenId && primaryCard.vProvisionedTokenId.trim() !== ''
    const hasCardNumber = (primaryCard.lastFour || primaryCard.cardNumber) &&
                          (primaryCard.lastFour || primaryCard.cardNumber).trim() !== ''
    const hasCardType = primaryCard.type && primaryCard.type.trim() !== ''

    console.log('🔍 Card validation:', { hasTokenId, hasCardNumber, hasCardType })

    // Return null if card is empty/placeholder (no token ID and no card number)
    if (!hasTokenId && !hasCardNumber) {
      console.log('🔍 Card is empty placeholder - returning null')
      return null
    }

    // Return card with VIC session IDs
    return {
      vProvisionedTokenId: primaryCard.vProvisionedTokenId,
      consumerId: primaryCard.consumerId,
      clientDeviceId: primaryCard.clientDeviceId,
      clientReferenceId: primaryCard.clientReferenceId,
      lastFour: primaryCard.lastFour || primaryCard.cardNumber,
      type: primaryCard.type,
      expirationDate: primaryCard.expirationDate
    }
  },

  /**
   * Get payment cards for user
   */
  async getPaymentCards(userId: string): Promise<PaymentCard[]> {
    try {
      const profile = await this.getUserProfile(userId)
      return profile?.paymentCards || []
    } catch {
      return []
    }
  },

  /**
   * Remove payment card from user profile
   */
  async removePaymentCard(
    userId: string,
    vProvisionedTokenId: string
  ): Promise<UserProfileData> {
    const existingProfile = await this.getUserProfile(userId)
    if (!existingProfile) {
      throw new Error('Profile not found')
    }

    const existingCards = existingProfile.paymentCards || []
    const updatedCards = existingCards.filter(
      card => card.vProvisionedTokenId !== vProvisionedTokenId
    )

    return await this.updateUserProfile(userId, {
      paymentCards: updatedCards
    } as any)
  },

  /**
   * Delete user profile
   */
  async deleteUserProfile(userId: string): Promise<void> {
    const existingProfile = await this.getUserProfile(userId)
    if (!existingProfile || !existingProfile.id) {
      return
    }

    const response = await client.models.UserProfile.delete({
      id: existingProfile.id
    })

    if (response.errors && response.errors.length > 0) {
      throw new Error(`Failed to delete user profile: ${response.errors[0].message}`)
    }
  }
}
