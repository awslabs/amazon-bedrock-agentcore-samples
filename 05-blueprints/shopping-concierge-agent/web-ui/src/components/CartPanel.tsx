import { useState, useEffect } from 'react'
import { getCartItems, removeCartItems, type CartItem } from '../services/cartService'

interface User {
  username: string
  email?: string
  userId: string
}

interface CartPanelProps {
  user: User
  isOpen: boolean
  onClose: () => void
  onCartUpdate?: () => void
  onPurchaseConfirm?: (cartItems: CartItem[]) => void
  refreshTrigger?: number // Add refresh trigger for manual refresh
}

const CartPanel = ({ user, isOpen, onClose, onCartUpdate, onPurchaseConfirm, refreshTrigger }: CartPanelProps) => {
  const [cartItems, setCartItems] = useState<CartItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [removingItems, setRemovingItems] = useState<Set<string>>(new Set())

  // Load cart items when panel opens
  const loadCartItems = async () => {
    try {
      setLoading(true)
      setError(null)
      const items = await getCartItems(user.userId)
      setCartItems(items)
    } catch (err) {
      console.error('Error loading cart items:', err)
      setError('Failed to load cart items')
    } finally {
      setLoading(false)
    }
  }

  // Remove item from cart
  const handleRemoveItem = async (item: CartItem) => {
    const identifier = item.asin

    if (!identifier || removingItems.has(identifier)) return

    try {
      setRemovingItems(prev => new Set(prev).add(identifier))

      await removeCartItems(user.userId, [item.asin])

      // Remove item from local state
      setCartItems(prev => prev.filter(i => i.asin !== identifier))
      
      // Notify parent to update cart count
      if (onCartUpdate) {
        onCartUpdate()
      }
    } catch (err) {
      console.error('Error removing item:', err)
      setError('Failed to remove item')
    } finally {
      setRemovingItems(prev => {
        const newSet = new Set(prev)
        newSet.delete(identifier)
        return newSet
      })
    }
  }

  // All items are products in shopping-only mode
  const getItemIcon = () => '📦'
  const getItemTypeLabel = () => 'Product'

  // Format price for display
  const formatPrice = (price: string) => {
    if (price.includes('$')) return price
    return `$${price}`
  }

  // Format reviews for display
  const formatReviews = (reviews?: string) => {
    if (!reviews || reviews === '') return 'No reviews'
    return `${reviews} ⭐`
  }

  // Load cart items when panel opens
  useEffect(() => {
    if (isOpen) {
      loadCartItems()
    }
  }, [isOpen, user.userId])

  // Refresh when refreshTrigger changes (triggered after purchase)
  useEffect(() => {
    if (refreshTrigger) {
      console.log('🔄 CartPanel: Refreshing cart after purchase')
      loadCartItems()
    }
  }, [refreshTrigger])

  // Auto-refresh cart while panel is open (poll every 3 seconds)
  useEffect(() => {
    if (!isOpen) return

    console.log('🔄 CartPanel: Starting auto-refresh polling (every 3 seconds)')
    const intervalId = setInterval(() => {
      console.log('🔄 CartPanel: Auto-refreshing cart...')
      loadCartItems()
    }, 3000) // Refresh every 3 seconds

    return () => {
      console.log('🔄 CartPanel: Stopping auto-refresh polling')
      clearInterval(intervalId)
    }
  }, [isOpen])

  // Calculate total items
  const totalItems = cartItems.reduce((sum, item) => sum + item.qty, 0)

  return (
    <div className={`fixed top-0 right-0 w-96 h-screen bg-white shadow-xl z-50 flex flex-col transition-transform duration-300 ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
      <div className="flex flex-col h-full">
        <div className="flex justify-between items-center p-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="flex items-center">
                <span className="text-xl">🛍️</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-800">Shopping Cart</h3>
            </div>
            {totalItems > 0 && (
              <span className="bg-blue-600 text-white px-2 py-0.5 rounded-full text-xs font-medium">{totalItems} item{totalItems !== 1 ? 's' : ''}</span>
            )}
          </div>
          <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500">
              <div className="loading-spinner"></div>
              <span>Loading cart...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500">
              <span className="text-3xl">⚠️</span>
              <span>{error}</span>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors" onClick={loadCartItems}>
                Retry
              </button>
            </div>
          ) : cartItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500">
              <div className="flex items-center text-4xl">
                <span>🛒</span>
              </div>
              <span>Your cart is empty</span>
              <span className="text-xs text-gray-400">Add products to get started</span>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {cartItems.map((item) => {
                const identifier = item.asin

                return (
                  <div key={identifier} className="flex gap-3 p-3 bg-gray-50 rounded-xl border border-gray-200">
                    <div className="text-2xl w-10 h-10 flex items-center justify-center bg-white rounded-lg border border-gray-200">{getItemIcon()}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1 mb-1">
                        <div className="inline-block px-1.5 py-0.5 bg-sky-100 text-sky-700 rounded text-[10px] font-semibold uppercase">{getItemTypeLabel()}</div>
                      </div>
                      <h4 className="text-sm font-medium text-gray-800 leading-tight">{item.title}</h4>
                      <div className="flex gap-3 mt-1 text-xs">
                        <span className="font-semibold text-blue-600">{formatPrice(item.price)}</span>
                        {item.qty > 1 && <span className="text-gray-500">Qty: {item.qty}</span>}
                      </div>

                      {item.reviews && (
                        <div className="text-xs text-gray-500 mt-1">{formatReviews(item.reviews)}</div>
                      )}
                    </div>

                    <div className="flex flex-col gap-2">
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="w-8 h-8 flex items-center justify-center bg-white border border-gray-200 rounded text-gray-500 hover:border-blue-600 hover:text-blue-600 transition-colors"
                          title="View on Amazon"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M18 13V19A2 2 0 0 1 16 21H5A2 2 0 0 1 3 19V8A2 2 0 0 1 5 6H11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M15 3H21V9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M10 14L21 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </a>
                      )}
                      
                      <button
                        className="w-8 h-8 flex items-center justify-center bg-white border border-gray-200 rounded text-gray-500 hover:border-red-500 hover:text-red-500 transition-colors disabled:opacity-50"
                        onClick={() => handleRemoveItem(item)}
                        disabled={removingItems.has(identifier)}
                        title="Remove from cart"
                      >
                        {removingItems.has(identifier) ? (
                          <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-blue-600 rounded-full animate-spin"></div>
                        ) : (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M3 6H5H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M8 6V4A2 2 0 0 1 10 2H14A2 2 0 0 1 16 4V6M19 6V20A2 2 0 0 1 17 22H7A2 2 0 0 1 5 20V6H19Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {!loading && !error && cartItems.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <button
                className="w-full flex items-center justify-center gap-2 py-3 px-6 bg-gradient-to-r from-blue-600 to-blue-800 text-white font-semibold rounded-lg hover:shadow-lg hover:-translate-y-0.5 transition-all"
                onClick={() => {
                  if (onPurchaseConfirm) {
                    onPurchaseConfirm(cartItems)
                  }
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M20 6L9 17L4 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Confirm Purchase
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CartPanel
