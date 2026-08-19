import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface CartItem {
  asin: string
  title: string
  price: string
  qty: number
  reviews?: string
  url?: string
}

export interface WishlistItem {
  id: string
  user_id: string
  asin: string
  title: string
  price: string
  reviews?: string
  url?: string
  createdAt?: string
  updatedAt?: string
}

/**
 * Get cart items for a user, grouped by ASIN with quantities
 * Mimics the logic from the Python get_cart() function
 */
export const getCartItems = async (userId: string): Promise<CartItem[]> => {
  try {
    // Query all wishlist items for the user with explicit field selection
    const response = await client.models.Wishlist.list({
      filter: {
        user_id: { eq: userId }
      },
      selectionSet: ['id', 'user_id', 'asin', 'title', 'price', 'reviews', 'url',
                     'createdAt', 'updatedAt'] as any
    })

    console.log('🛒 Cart Service: Full GraphQL response:', {
      data: response.data,
      errors: response.errors,
      extensions: response.extensions,
      nextToken: response.nextToken
    })

    // Log detailed error information
    if (response.errors && response.errors.length > 0) {
      console.log('🚨 Cart Service: GraphQL Errors Details:')
      response.errors.forEach((error, index) => {
        console.log(`Error ${index + 1}:`, { // nosemgrep
          message: error.message,
          locations: error.locations,
          path: error.path,
          extensions: error.extensions
        })
      })
    }

    if (!response.data) {
      console.log('🛒 Cart Service: No data in response, returning empty array')
      return []
    }

    const items = response.data as WishlistItem[]

    // Log the first few items to see their structure
    console.log('🛒 Cart Service: First 3 items:', items.slice(0, 3))
    console.log('🛒 Cart Service: Items array length:', items.length)
    console.log('🛒 Cart Service: Items array:', items)

    // Filter out any null/undefined items and ensure required fields exist
    // Handle both regular format and DynamoDB format with type descriptors
    const validItems = items.filter(item => {
      if (!item) return false
      
      // Check for regular format or DynamoDB format
      const title = item.title || (item.title as any)?.S
      const price = item.price || (item.price as any)?.S
      const user_id = item.user_id || (item.user_id as any)?.S
      
      const isValid = title && price && user_id
      
      if (!isValid) {
        console.log('🛒 Cart Service: Invalid item:', {
          hasTitle: !!title,
          hasPrice: !!price,
          hasUserId: !!user_id,
          item: item
        })
      }
      
      return isValid
    })

    console.log(`🛒 Cart Service: Found ${items.length} total items, ${validItems.length} valid items`)

    // Helper function to extract value from either regular or DynamoDB format
    const getValue = (field: any): string => {
      if (typeof field === 'string') return field
      if (field && typeof field === 'object' && field.S) return field.S
      return ''
    }

    // Group items by ASIN
    const itemGroups: Record<string, { items: any[], latestItem: any }> = {}

    for (const item of validItems) {
      const key = getValue(item.asin)

      if (!itemGroups[key]) {
        itemGroups[key] = {
          items: [],
          latestItem: item
        }
      }
      itemGroups[key].items.push(item)

      // Keep the latest item (most recent createdAt)
      const itemCreatedAt = getValue(item.createdAt)
      const latestCreatedAt = getValue(itemGroups[key].latestItem.createdAt)

      if (itemCreatedAt && latestCreatedAt) {
        if (itemCreatedAt > latestCreatedAt) {
          itemGroups[key].latestItem = item
        }
      }
    }

    // Convert to expected format
    const cartItems: CartItem[] = []
    for (const [_key, group] of Object.entries(itemGroups)) {
      const latest = group.latestItem

      const cartItem: CartItem = {
        asin: getValue(latest.asin),
        title: getValue(latest.title),
        price: getValue(latest.price),
        // If agent accidentally adds duplicates, they'll be grouped and counted here
        qty: group.items.length,
        reviews: getValue(latest.reviews) || '',
        url: getValue(latest.url) || ''
      }

      cartItems.push(cartItem)
    }

    // Sort by ASIN
    cartItems.sort((a, b) => a.asin.localeCompare(b.asin))
    return cartItems

  } catch (error) {
    console.error('Error getting cart items:', error)
    throw new Error(`Failed to get cart items: ${error}`)
  }
}

/**
 * Remove specific items from the cart by their ASINs
 */
export const removeCartItems = async (
  userId: string,
  asins: string[]
): Promise<void> => {
  try {
    // Get all items for the user first with explicit field selection
    const response = await client.models.Wishlist.list({
      filter: {
        user_id: { eq: userId }
      },
      selectionSet: ['id', 'user_id', 'asin', 'title', 'price', 'reviews', 'url',
                     'createdAt', 'updatedAt'] as any
    })

    if (!response.data) {
      return
    }

    const items = response.data as WishlistItem[]

    // Find items to delete that match the ASINs
    const itemsToDelete = items.filter(item => asins.includes(item.asin))

    // Delete each item using the id (primary key)
    const deletePromises = itemsToDelete.map(item =>
      client.models.Wishlist.delete({
        id: item.id
      })
    )

    await Promise.all(deletePromises)
    console.log(`🛒 Removed ${itemsToDelete.length} purchased items from cart`)

  } catch (error) {
    console.error('Error removing cart items:', error)
    throw new Error(`Failed to remove cart items: ${error}`)
  }
}

/**
 * Get the total number of items in the cart (for badge display)
 */
export const getCartItemCount = async (userId: string): Promise<number> => {
  try {
    const cartItems = await getCartItems(userId)
    return cartItems.reduce((total, item) => total + item.qty, 0)
  } catch (error) {
    console.error('Error getting cart item count:', error)
    return 0
  }
}

/**
 * Add an item to the cart (wishlist)
 */
export const addToCart = async (
  userId: string,
  asin: string,
  title: string,
  price: string,
  reviews?: string,
  url?: string
): Promise<void> => {
  try {
    console.log('🛒 Cart Service: Adding item to cart:', { userId, asin, title, price })

    const response = await client.models.Wishlist.create({
      user_id: userId,
      asin,
      title,
      price,
      reviews: reviews || '',
      url: url || ''
    })

    if (response.errors && response.errors.length > 0) {
      console.error('🚨 Cart Service: GraphQL Errors:', response.errors)
      throw new Error(`Failed to add item to cart: ${response.errors[0].message}`)
    }

    console.log('🛒 Cart Service: Successfully added item to cart:', response.data)
    
  } catch (error) {
    console.error('Error adding item to cart:', error)
    throw new Error(`Failed to add item to cart: ${error}`)
  }
}


/**
 * Clear all items from the cart (after successful purchase)
 */
export const clearCart = async (userId: string): Promise<void> => {
  try {
    // Get all items for the user
    const response = await client.models.Wishlist.list({
      filter: {
        user_id: { eq: userId }
      },
      selectionSet: ['id'] as any
    })

    if (!response.data || response.data.length === 0) {
      console.log('🛒 Cart already empty')
      return
    }

    // Delete all items
    const deletePromises = response.data.map(item => 
      client.models.Wishlist.delete({ id: item.id })
    )

    await Promise.all(deletePromises)
    console.log(`🛒 Cleared ${response.data.length} items from cart`)

  } catch (error) {
    console.error('Error clearing cart:', error)
    throw new Error(`Failed to clear cart: ${error}`)
  }
}
