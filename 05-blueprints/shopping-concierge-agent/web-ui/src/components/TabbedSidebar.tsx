import React, { useState, useEffect } from 'react';
import { getWishlistItems, deleteWishlistItem, type WishlistItem } from '../services/wishlistService';
import { getBookings, type BookingItem } from '../services/bookingsService';

interface TabbedSidebarProps {
  user: any;
  messages?: any[];
  refreshTrigger?: number;
}

const getIcon = (): string => {
  return '📦';
};

const TabbedSidebar: React.FC<TabbedSidebarProps> = ({ user, messages = [], refreshTrigger }) => {
  const [activeTab, setActiveTab] = useState<'shopping' | 'purchases'>('shopping');
  const [wishlistItems, setWishlistItems] = useState<WishlistItem[]>([]);
  const [bookings, setBookings] = useState<BookingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [removingItems, setRemovingItems] = useState<Set<string>>(new Set());


  const loadWishlist = async () => {
    setLoading(true);
    try {
      const items = await getWishlistItems(user.userId);
      const validItems = items.filter(item => item && item.type && item.title);
      setWishlistItems(validItems);
    } catch (error) {
      console.error('Error loading wishlist:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadBookings = async () => {
    try {
      const items = await getBookings(user.userId);
      setBookings(items);
    } catch (error) {
      console.error('Error loading bookings:', error);
    }
  };

  const productItems = wishlistItems;

  useEffect(() => {
    loadWishlist();
    loadBookings();
  }, [user.userId]);

  // Refresh when a new assistant message completes
  const completedCount = messages.filter(m => m.role === 'assistant' && !m.isStreaming).length;
  useEffect(() => {
    if (completedCount > 0) {
      loadWishlist();
      loadBookings();
    }
  }, [completedCount]);

  // Refresh when refreshTrigger changes (triggered after purchase)
  useEffect(() => {
    if (refreshTrigger) {
      console.log('🔄 TabbedSidebar: Refreshing after purchase');
      loadWishlist();
      loadBookings();
    }
  }, [refreshTrigger]);

  const handleDelete = async (id: string) => {
    if (removingItems.has(id)) return;

    try {
      setRemovingItems(prev => new Set(prev).add(id));
      const success = await deleteWishlistItem(id);
      if (success) {
        setWishlistItems(prev => prev.filter(item => item.id !== id));
      }
    } catch (error) {
      console.error('Error deleting item:', error);
    } finally {
      setRemovingItems(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };



  const TabButton = ({ tab, icon, label }: { tab: typeof activeTab; icon: React.ReactNode; label: string }) => (
    <button
      className={`flex items-center gap-1.5 px-2.5 py-1.5 text-sm transition-colors ${
        activeTab === tab
          ? 'text-[#1668e3] border-b-2 border-[#1668e3] -mb-px'
          : 'text-gray-500 hover:text-gray-700'
      }`}
      onClick={() => setActiveTab(tab)}
    >
      {icon}
      {label}
    </button>
  );

  const WishlistCard = ({ item, showType = true }: { item: WishlistItem; showType?: boolean }) => (
    <div
      className={`bg-gray-50 rounded-lg p-3 border border-gray-100 transition-all ${item.url ? 'cursor-pointer hover:border-blue-300' : 'hover:border-gray-200'}`}
      onClick={() => item.url && window.open(item.url, '_blank')}
    >
      <div className="flex items-start gap-3">
        <div className="text-xl w-8 h-8 flex items-center justify-center bg-white rounded-lg border border-gray-100">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-gray-900 truncate">{item.title}</div>
          {showType && (
            <span className="inline-block px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium uppercase mt-1">
              {item.type}
            </span>
          )}
        </div>
        <button
          className="w-8 h-8 flex items-center justify-center bg-white border border-gray-200 rounded text-gray-500 hover:border-red-500 hover:text-red-500 transition-colors disabled:opacity-50"
          onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
          disabled={removingItems.has(item.id)}
          title="Remove from list"
        >
          {removingItems.has(item.id) ? (
            <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-blue-600 rounded-full animate-spin"></div>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 6H5H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M8 6V4A2 2 0 0 1 10 2H14A2 2 0 0 1 16 4V6M19 6V20A2 2 0 0 1 17 22H7A2 2 0 0 1 5 20V6H19Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </button>
      </div>

      {item.type === 'product' && item.asin && (
        <div className="text-xs text-gray-500 mt-2">
          ASIN: {item.asin}
          {item.reviews && <span className="ml-2">⭐ {item.reviews}</span>}
        </div>
      )}

      {item.details && (
        <p className="text-sm text-gray-600 mt-2 line-clamp-2">{item.details}</p>
      )}

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        {item.price && (
          <div className="text-sm font-semibold text-[#1668e3]">{item.price}</div>
        )}
        {item.url && (
          <span className="text-xs text-blue-600">
            View on Amazon →
          </span>
        )}
      </div>
    </div>
  );

  return (
    <div className="w-1/2 flex flex-col bg-white m-3 ml-0 rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      {/* Tab Navigation */}
      <div className="flex gap-4 px-4 py-2 bg-[#f0f4ff] border-b border-gray-200 overflow-x-auto">
        <TabButton tab="shopping" label="Shopping List" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 2L7 6H3L5 20H19L21 6H17L15 2H9Z"/>
            <path d="M9 6V4C9 3.44772 9.44772 3 10 3H14C14.5523 3 15 3.44772 15 4V6"/>
          </svg>
        } />
        <TabButton tab="purchases" label="Purchases" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 11L12 14L22 4"/>
            <path d="M21 12V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H16"/>
          </svg>
        } />
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'shopping' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">🛍️ Shopping List</h3>
              <button
                onClick={loadWishlist}
                disabled={loading}
                className="p-2 text-gray-500 hover:text-[#1668e3] hover:bg-gray-100 rounded-lg transition-colors"
                title="Refresh"
              >
                {loading ? '⟳' : '↻'}
              </button>
            </div>
            {loading ? (
              <p className="text-gray-500 text-center py-8">Loading...</p>
            ) : productItems.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No shopping items yet. Ask the agent to search for products or create a packing list!</p>
            ) : (
              <div className="space-y-3">
                {productItems.map(item => <WishlistCard key={item.id} item={item} showType={true} />)}
              </div>
            )}
          </div>
        )}

        {activeTab === 'purchases' && (
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">✅ Order History</h3>
            {bookings.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No purchases yet. Complete a purchase to see your order history!</p>
            ) : (
              <div className="space-y-3">
                {bookings.map((booking) => (
                  <div
                    key={booking.id}
                    className={`bg-white rounded-xl p-4 border border-gray-200 shadow-sm ${booking.url ? 'cursor-pointer hover:border-blue-300' : ''}`}
                    onClick={() => booking.url && window.open(booking.url, '_blank')}
                  >
                    <div className="flex items-start gap-3">
                      <div className="text-2xl">{getIcon()}</div>
                      <div className="flex-1">
                        <div className="font-semibold text-gray-900">{booking.title}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {booking.item_type === 'product' && booking.asin && (
                            <span>ASIN: {booking.asin}</span>
                          )}
                        </div>
                        {booking.purchase_date && (
                          <div className="text-xs text-gray-400 mt-1">
                            Purchased: {new Date(booking.purchase_date).toLocaleDateString()}
                          </div>
                        )}
                        <div className="flex items-center justify-between mt-2">
                          <span className="text-sm font-semibold text-[#1668e3]">{booking.price}</span>
                          <span className="text-xs text-gray-400">Order: {booking.order_id}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TabbedSidebar;
