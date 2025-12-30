import { useState, useEffect, useCallback } from 'react'
import { getCartItemCount } from '../services/cartService'

/**
 * Custom hook for managing cart state
 */
export const useCart = (userId: string) => {
  const [cartItemCount, setCartItemCount] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Function to refresh cart count
  const refreshCartCount = useCallback(async () => {
    if (!userId) {
      setCartItemCount(0)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const count = await getCartItemCount(userId)
      setCartItemCount(count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get cart count')
      setCartItemCount(0)
    } finally {
      setLoading(false)
    }
  }, [userId])

  // Load cart count on mount and when userId changes
  useEffect(() => {
    refreshCartCount()
  }, [refreshCartCount])

  return {
    cartItemCount,
    loading,
    error,
    refreshCartCount
  }
}
