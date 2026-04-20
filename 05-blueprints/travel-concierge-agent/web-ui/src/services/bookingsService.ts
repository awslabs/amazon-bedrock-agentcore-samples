import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>()

export interface BookingItem {
  id: string
  user_id: string
  order_id: string
  item_type: 'flight' | 'hotel' | 'product'
  title: string
  price: string
  purchase_date?: string
  flight_id?: string
  origin?: string
  destination?: string
  departure_date?: string
  airline?: string
  hotel_id?: string
  city_code?: string
  rating?: string
  amenities?: string
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
        'flight_id', 'origin', 'destination', 'departure_date', 'airline',
        'hotel_id', 'city_code', 'rating', 'amenities', 'asin', 'url'
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
 * Create a booking record after successful purchase
 */
export const createBooking = async (
  userId: string,
  orderId: string,
  item: {
    item_type: 'flight' | 'hotel' | 'product'
    title: string
    price: string
    asin?: string
    url?: string
    // Flight fields
    flight_id?: string
    origin?: string
    destination?: string
    departure_date?: string
    airline?: string
    // Hotel fields
    hotel_id?: string
    city_code?: string
    rating?: string
    amenities?: string
  }
): Promise<BookingItem | null> => {
  try {
    const response = await client.models.Bookings.create({
      user_id: userId,
      order_id: orderId,
      item_type: item.item_type,
      title: item.title,
      price: item.price,
      purchase_date: new Date().toISOString(),
      asin: item.asin,
      url: item.url,
      flight_id: item.flight_id,
      origin: item.origin,
      destination: item.destination,
      departure_date: item.departure_date,
      airline: item.airline,
      hotel_id: item.hotel_id,
      city_code: item.city_code,
      rating: item.rating,
      amenities: item.amenities
    })

    console.log('📋 Booking created:', response.data)
    return response.data as BookingItem
  } catch (error) {
    console.error('Error creating booking:', error)
    return null
  }
}
