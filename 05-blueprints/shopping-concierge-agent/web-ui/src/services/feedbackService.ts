import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface FeedbackData {
  messageId: string;
  feedback: 'up' | 'down';
  userId: string;
  comment?: string;
}

/**
 * Submit feedback for a chat message using AppSync GraphQL
 */
export const submitFeedback = async (
  messageId: string,
  feedback: 'up' | 'down',
  userId: string,
  comment?: string
): Promise<void> => {
  try {
    console.log('Submitting feedback:', { messageId, feedback, userId, comment })

    const response = await client.models.Feedback.create({
      messageId,
      userId,
      feedback,
      comment: comment || '',
    })

    if (response.errors && response.errors.length > 0) {
      console.error('GraphQL errors:', response.errors)
      throw new Error(`Failed to submit feedback: ${response.errors[0].message}`)
    }

    console.log('Feedback submitted successfully:', response.data)
    
  } catch (error) {
    console.error('Error submitting feedback:', error)
    throw error
  }
}

/**
 * Get feedback for a specific message
 */
export const getFeedbackForMessage = async (messageId: string) => {
  try {
    const response = await client.models.Feedback.list({
      filter: {
        messageId: { eq: messageId }
      }
    })

    if (response.errors && response.errors.length > 0) {
      console.error('GraphQL errors:', response.errors)
      throw new Error(`Failed to get feedback: ${response.errors[0].message}`)
    }

    return response.data || []
    
  } catch (error) {
    console.error('Error getting feedback:', error)
    throw error
  }
}

/**
 * Get all feedback for a user
 */
export const getUserFeedback = async (userId: string) => {
  try {
    const response = await client.models.Feedback.list({
      filter: {
        userId: { eq: userId }
      }
    })

    if (response.errors && response.errors.length > 0) {
      console.error('GraphQL errors:', response.errors)
      throw new Error(`Failed to get user feedback: ${response.errors[0].message}`)
    }

    return response.data || []
    
  } catch (error) {
    console.error('Error getting user feedback:', error)
    throw error
  }
}
