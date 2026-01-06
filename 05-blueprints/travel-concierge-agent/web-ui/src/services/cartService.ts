import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface CartItem {
  asin: string
  item_type?: 'product' | 'hotel' | 'flight'
  title: string
  price: string
  qty: number
  reviews?: string
  url?: string
  details?: {
    // Hotel fields
    hotel_id?: string
    city_code?: string
    rating?: string
    amenities?: string
    // Flight fields
    flight_id?: string
    origin?: string
    destination?: string
    departure_date?: string
    airline?: string
  }
}

export interface WishlistItem {
  id: string
  user_id: string
  asin: string
  item_type?: string
  title: string
  price: string
  reviews?: string
  url?: string
  // Hotel fields
  hotel_id?: string
  city_code?: string
  rating?: string
  amenities?: string
  // Flight fields
  flight_id?: string
  origin?: string
  destination?: string
  departure_date?: string
  airline?: string
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
      selectionSet: ['id', 'user_id', 'asin', 'item_type', 'title', 'price', 'reviews', 'url',
                     'hotel_id', 'city_code', 'rating', 'amenities',
                     'flight_id', 'origin', 'destination', 'departure_date', 'airline',
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

    // Group items by unique identifier (asin for products, composite key for hotels/flights)
    const itemGroups: Record<string, { items: any[], latestItem: any }> = {}

    for (const item of validItems) {
      const itemType = getValue(item.item_type) || 'product'

      // Create unique key based on item type
      let key: string
      if (itemType === 'product') {
        // Products: group by ASIN
        key = getValue(item.asin)
      } else if (itemType === 'hotel') {
        // Hotels: group by hotel_id + city_code (same hotel in same city = duplicate)
        const hotelId = getValue(item.hotel_id)
        const cityCode = getValue(item.city_code)
        key = `hotel_${hotelId}_${cityCode}`
      } else if (itemType === 'flight') {
        // Flights: group by origin + destination + departure_date (same route on same day = duplicate)
        const origin = getValue(item.origin)
        const destination = getValue(item.destination)
        const departureDate = getValue(item.departure_date)
        key = `flight_${origin}_${destination}_${departureDate}`
      } else {
        key = getValue(item.asin)
      }

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
      const itemType = getValue(latest.item_type) || 'product'
      
      const cartItem: CartItem = {
        asin: getValue(latest.asin),
        item_type: itemType as 'product' | 'hotel' | 'flight',
        title: getValue(latest.title),
        price: getValue(latest.price),
        // For all item types, count the number of grouped items
        // If agent accidentally adds duplicates, they'll be grouped and counted here
        qty: group.items.length,
        reviews: getValue(latest.reviews) || '',
        url: getValue(latest.url) || ''
      }
      
      // Add type-specific details
      if (itemType === 'hotel') {
        cartItem.details = {
          hotel_id: getValue(latest.hotel_id),
          city_code: getValue(latest.city_code),
          rating: getValue(latest.rating),
          amenities: getValue(latest.amenities)
        }
      } else if (itemType === 'flight') {
        cartItem.details = {
          flight_id: getValue(latest.flight_id),
          origin: getValue(latest.origin),
          destination: getValue(latest.destination),
          departure_date: getValue(latest.departure_date),
          airline: getValue(latest.airline)
        }
      }
      
      cartItems.push(cartItem)
    }

    // Sort by item type, then by identifier
    cartItems.sort((a, b) => {
      if (a.item_type !== b.item_type) {
        return (a.item_type || 'product').localeCompare(b.item_type || 'product')
      }
      return a.asin.localeCompare(b.asin)
    })
    return cartItems

  } catch (error) {
    console.error('Error getting cart items:', error)
    throw new Error(`Failed to get cart items: ${error}`)
  }
}

/**
 * Remove specific items from the cart by their identifiers
 * Supports products (by asin), flights (by flight_id), and hotels (by hotel_id)
 */
export const removeCartItems = async (
  userId: string, 
  identifiers: { asins?: string[], flight_ids?: string[], hotel_ids?: string[] }
): Promise<void> => {
  try {
    const { asins = [], flight_ids = [], hotel_ids = [] } = identifiers

    // Get all items for the user first with explicit field selection
    const response = await client.models.Wishlist.list({
      filter: {
        user_id: { eq: userId }
      },
      selectionSet: ['id', 'user_id', 'asin', 'item_type', 'title', 'price', 'reviews', 'url',
                     'hotel_id', 'city_code', 'rating', 'amenities',
                     'flight_id', 'origin', 'destination', 'departure_date', 'airline',
                     'createdAt', 'updatedAt'] as any
    })

    if (!response.data) {
      return
    }

    const items = response.data as WishlistItem[]
    
    // Find items to delete that match any of the identifiers
    const itemsToDelete = items.filter(item => {
      const itemType = item.item_type || 'product'
      
      if (itemType === 'flight' && item.flight_id && flight_ids.includes(item.flight_id)) {
        return true
      }
      if (itemType === 'hotel' && item.hotel_id && hotel_ids.includes(item.hotel_id)) {
        return true
      }
      if (item.asin && asins.includes(item.asin)) {
        return true
      }
      return false
    })
    
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
