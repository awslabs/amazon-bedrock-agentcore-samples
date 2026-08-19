import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface ItineraryItem {
  id: string
  user_id: string
  type: 'flight' | 'hotel' | 'activity' | 'restaurant' | 'transport'
  title: string
  location?: string
  price?: string
  date?: string
  time_of_day?: 'morning' | 'afternoon' | 'evening'
  details?: string
  description?: string
  createdAt?: string
  updatedAt?: string
}

export const getItineraryItems = async (userId: string): Promise<ItineraryItem[]> => {
  try {
    console.log('🗂️ Fetching itinerary and cart items for userId:', userId);
    
    // Fetch from Itinerary table
    const itineraryResponse = await client.models.Itinerary.list({
      filter: {
        user_id: { eq: userId }
      }
    })

    // Fetch from Wishlist table (cart items)
    const wishlistResponse = await client.models.Wishlist.list({
      filter: {
        user_id: { eq: userId }
      }
    })

    console.log('🗂️ Itinerary response:', {
      data: itineraryResponse.data,
      errors: itineraryResponse.errors,
      count: itineraryResponse.data?.length || 0
    });
    console.log('🛒 Wishlist response:', {
      data: wishlistResponse.data,
      errors: wishlistResponse.errors,
      count: wishlistResponse.data?.length || 0
    });

    const itineraryItems = itineraryResponse.data || []
    const wishlistItems = wishlistResponse.data || []

    console.log(`🗂️ Found ${itineraryItems.length} itinerary items, ${wishlistItems.length} wishlist items`);

    // Convert wishlist items to itinerary format
    const convertedWishlistItems = wishlistItems
      .filter(item => item.item_type === 'flight' || item.item_type === 'hotel')
      .map(item => ({
        id: item.id,
        user_id: item.user_id,
        type: item.item_type as 'flight' | 'hotel',
        title: item.title,
        location: item.item_type === 'hotel' ? item.city_code : `${item.origin} → ${item.destination}`,
        price: item.price,
        date: item.departure_date || undefined,
        details: item.item_type === 'flight' 
          ? `${item.airline || ''} - ${item.origin} to ${item.destination}`.trim()
          : item.amenities || '',
        createdAt: item.createdAt,
        updatedAt: item.updatedAt
      }))

    // Combine both sources and deduplicate by id
    const allItems = [...itineraryItems, ...convertedWishlistItems] as ItineraryItem[]
    
    // Remove duplicates based on id
    const uniqueItems = Array.from(
      new Map(allItems.map(item => [item.id, item])).values()
    )

    console.log('Combined items (deduplicated):', uniqueItems);
    return uniqueItems
  } catch (error) {
    console.error('Error fetching itinerary:', error)
    return []
  }
}

export const deleteItineraryItem = async (itemId: string): Promise<boolean> => {
  console.log('🗑️ Attempting to delete item:', itemId)
  try {
    // Try deleting from both tables - Amplify doesn't error if item doesn't exist
    const [itineraryResult, wishlistResult] = await Promise.all([
      client.models.Itinerary.delete({ id: itemId }),
      client.models.Wishlist.delete({ id: itemId })
    ])
    console.log('🗑️ Itinerary delete result:', itineraryResult)
    console.log('🗑️ Wishlist delete result:', wishlistResult)
    return true
  } catch (error) {
    console.error('❌ Error deleting itinerary item:', error)
    return false
  }
}
