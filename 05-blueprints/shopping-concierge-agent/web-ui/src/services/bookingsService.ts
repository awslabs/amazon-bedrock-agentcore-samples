import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface BookingItem {
  id: string
  user_id: string
  order_id: string
  item_type: 'product'  // Shopping-only: products only
  title: string
  price: string
  purchase_date?: string
  asin?: string
  url?: string
}

export const getBookings = async (userId: string): Promise<BookingItem[]> => {
  try {
    console.log('📋 Fetching bookings for user:', userId)
    const response = await client.models.Bookings.list({
      filter: {
        user_id: { eq: userId }
      },
      selectionSet: [
        'id', 'user_id', 'order_id', 'item_type', 'title', 'price', 'purchase_date',
        'asin', 'url'
      ] as any
    })

    console.log('📋 Bookings response:', response.data?.length || 0, 'items')
    if (response.errors) {
      console.error('📋 Bookings errors:', response.errors)
    }
    return (response.data || []) as BookingItem[]
  } catch (error) {
    console.error('📋 Error fetching bookings:', error)
    return []
  }
}

/**
 * Create a booking record after successful purchase (shopping-only: products)
 */
export const createBooking = async (
  userId: string,
  orderId: string,
  item: {
    title: string
    price: string
    asin?: string
    url?: string
  }
): Promise<BookingItem | null> => {
  try {
    const response = await client.models.Bookings.create({
      user_id: userId,
      order_id: orderId,
      item_type: 'product',  // Always 'product' for shopping-only
      title: item.title,
      price: item.price,
      purchase_date: new Date().toISOString(),
      asin: item.asin,
      url: item.url
    })

    console.log('📋 Booking created:', response.data)
    return response.data ? (response.data as unknown as BookingItem) : null
  } catch (error) {
    console.error('Error creating booking:', error)
    return null
  }
}
