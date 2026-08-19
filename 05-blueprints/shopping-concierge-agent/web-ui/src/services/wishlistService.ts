import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface WishlistItem {
  id: string
  user_id: string
  type: 'product'
  title: string
  price?: string
  details?: string
  asin?: string
  reviews?: string
  url?: string
  createdAt?: string
  updatedAt?: string
}

export const getWishlistItems = async (userId: string): Promise<WishlistItem[]> => {
  try {
    console.log('🛒 Fetching wishlist items for userId:', userId)

    const wishlistResponse = await client.models.Wishlist.list({
      filter: {
        user_id: { eq: userId }
      }
    })

    console.log('🛒 Wishlist response:', {
      count: wishlistResponse.data?.length || 0
    })

    const wishlistItems = wishlistResponse.data || []

    // Map to wishlist items (all items are products in shopping-only mode)
    const productItems = wishlistItems.map(item => ({
      id: item.id,
      user_id: item.user_id,
      type: 'product' as const,
      title: item.title,
      price: item.price,
      asin: item.asin || undefined,
      reviews: item.reviews || undefined,
      url: item.url || undefined,
      details: item.reviews || '',
      createdAt: item.createdAt,
      updatedAt: item.updatedAt
    }))

    console.log(`🛒 Found ${productItems.length} wishlist items`)
    return productItems
  } catch (error) {
    console.error('Error fetching wishlist:', error)
    return []
  }
}

export const deleteWishlistItem = async (itemId: string): Promise<boolean> => {
  console.log('🗑️ Attempting to delete wishlist item:', itemId)
  try {
    const result = await client.models.Wishlist.delete({ id: itemId })
    console.log('🗑️ Delete result:', result)
    return true
  } catch (error) {
    console.error('❌ Error deleting wishlist item:', error)
    return false
  }
}
