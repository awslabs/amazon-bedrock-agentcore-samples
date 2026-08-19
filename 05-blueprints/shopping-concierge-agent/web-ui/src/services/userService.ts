import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

// Create client function to ensure Amplify is configured before use
const getClient = () => generateClient<Schema>()

export interface SimpleUser {
  id: string
  createdAt: string
  updatedAt: string
}

/**
 * Get user record from the User table
 */
export const getUser = async (userId: string): Promise<SimpleUser | null> => {
  try {
    const client = getClient()
    const result = await client.models.User.get({ id: userId })
    
    if (result.errors) {
      console.error('GraphQL errors:', result.errors)
      return null
    }
    
    if (!result.data) {
      return null
    }

    const userData = result.data as any

    return {
      id: userData.id,
      createdAt: userData.createdAt || new Date().toISOString(),
      updatedAt: userData.updatedAt || new Date().toISOString(),
    }
  } catch (error) {
    console.error('Error fetching user:', error)
    return null
  }
}

/**
 * Create a new user record in the User table
 */
export const createUser = async (userId: string): Promise<SimpleUser | null> => {
  try {
    const client = getClient()
    const now = new Date().toISOString()
    
    const result = await client.models.User.create({
      id: userId,
      createdAt: now,
      updatedAt: now,
    })
    
    if (result.errors) {
      console.error('GraphQL errors:', result.errors)
      throw new Error('Failed to create user')
    }
    
    if (!result.data) {
      throw new Error('No data returned from user creation')
    }

    const userData = result.data as any

    return {
      id: userData.id,
      createdAt: userData.createdAt || now,
      updatedAt: userData.updatedAt || now,
    }
  } catch (error) {
    console.error('Error creating user:', error)
    throw error
  }
}

/**
 * Ensure user exists in the User table - creates if doesn't exist
 * This is needed for the relationship with ChatSession to work
 */
export const ensureUserExists = async (userId: string): Promise<SimpleUser> => {
  try {
    // First, try to get existing user
    let user = await getUser(userId)
    
    if (!user) {
      // User doesn't exist, create new record
      console.log('Creating new user record for:', userId)
      user = await createUser(userId)
      
      if (!user) {
        throw new Error('Failed to create user')
      }
    }
    
    return user
  } catch (error) {
    console.error('Error ensuring user exists:', error)
    throw error
  }
}
