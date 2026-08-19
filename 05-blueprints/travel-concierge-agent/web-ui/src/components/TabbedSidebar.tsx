import React, { useState, useEffect } from 'react';
import { getItineraryItems, deleteItineraryItem, type ItineraryItem } from '../services/itineraryService';
import { getBookings, type BookingItem } from '../services/bookingsService';

interface TabbedSidebarProps {
  user: any;
  messages?: any[];
  refreshTrigger?: number; // Add refresh trigger for manual refresh
}

const getIcon = (type: string): string => {
  const icons: Record<string, string> = {
    flight: '✈️',
    hotel: '🏨',
    activity: '🎭',
    restaurant: '🍽️',
    transport: '🚗'
  };
  return icons[type] || '📍';
};

const getTimeOfDayLabel = (timeOfDay: string): string => {
  const labels: Record<string, string> = {
    morning: '🌅 Morning',
    afternoon: '☀️ Afternoon',
    evening: '🌙 Evening'
  };
  return labels[timeOfDay] || timeOfDay;
};

const getTimeOfDayOrder = (timeOfDay?: string): number => {
  const order: Record<string, number> = {
    morning: 0,
    afternoon: 1,
    evening: 2
  };
  return order[timeOfDay || ''] ?? 3; // Items without time_of_day go last
};

const TabbedSidebar: React.FC<TabbedSidebarProps> = ({ user, messages = [], refreshTrigger }) => {
  const [activeTab, setActiveTab] = useState<'itinerary' | 'hotels' | 'flights' | 'map' | 'bookings'>('itinerary');
  const [itineraryItems, setItineraryItems] = useState<ItineraryItem[]>([]);
  const [bookings, setBookings] = useState<BookingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<string>('');
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [collapsedDays, setCollapsedDays] = useState<Set<string>>(new Set());
  const [removingItems, setRemovingItems] = useState<Set<string>>(new Set());


  const loadItinerary = async () => {
    setLoading(true);
    try {
      const items = await getItineraryItems(user.userId);
      const validItems = items.filter(item => item && item.type && item.title);
      validItems.sort((a, b) => {
        if (!a.date && !b.date) return 0;
        if (!a.date) return 1;
        if (!b.date) return -1;
        return a.date.localeCompare(b.date);
      });
      setItineraryItems(validItems);
    } catch (error) {
      console.error('Error loading itinerary:', error);
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

  // Filter out purchased items (bookings) from Hotels/Flights tabs
  // Bookings should only appear in Bookings tab
  // Match by flight_id/hotel_id or by title as fallback
  const purchasedFlightIds = new Set(bookings.filter(b => b.flight_id).map(b => b.flight_id));
  const purchasedHotelIds = new Set(bookings.filter(b => b.hotel_id).map(b => b.hotel_id));
  const purchasedTitles = new Set(bookings.map(b => b.title.trim().toLowerCase()));

  const isItemPurchased = (item: ItineraryItem): boolean => {
    // Check if item details contain flight_id or hotel_id that was purchased
    const itemTitleLower = item.title.trim().toLowerCase();

    // Match by title (primary - most reliable)
    if (purchasedTitles.has(itemTitleLower)) {
      return true;
    }

    // Match flights by flight_id in details
    if (item.type === 'flight' && item.details) {
      for (const flightId of purchasedFlightIds) {
        if (item.details.includes(flightId!)) {
          return true;
        }
      }
    }

    // Match hotels by hotel_id in details or location
    if (item.type === 'hotel') {
      for (const hotelId of purchasedHotelIds) {
        if (item.details?.includes(hotelId!) || item.location?.includes(hotelId!)) {
          return true;
        }
      }
    }

    return false;
  };

  const hotelItems = itineraryItems.filter(item =>
    item.type === 'hotel' && !isItemPurchased(item)
  );
  const flightItems = itineraryItems.filter(item =>
    item.type === 'flight' && !isItemPurchased(item)
  );

  // Group items by day, then by time_of_day within each day
  const groupedItems = itineraryItems.reduce((groups, item) => {
    const day = item.date || 'No Date';
    if (!groups[day]) groups[day] = {};

    const timeOfDay = item.time_of_day || 'unscheduled';
    if (!groups[day][timeOfDay]) groups[day][timeOfDay] = [];
    groups[day][timeOfDay].push(item);

    return groups;
  }, {} as Record<string, Record<string, ItineraryItem[]>>);

  useEffect(() => {
    loadItinerary();
    loadBookings();
  }, [user.userId]);

  // Refresh when a new assistant message completes (stops streaming)
  const completedAssistantCount = messages.filter(m => m.role === 'assistant' && !m.isStreaming).length;
  useEffect(() => {
    if (completedAssistantCount > 0) {
      console.log('🔄 TabbedSidebar: Refreshing after assistant message completed');
      loadItinerary();
      loadBookings();
    }
  }, [completedAssistantCount]);

  // Refresh when refreshTrigger changes (triggered after purchase)
  useEffect(() => {
    if (refreshTrigger) {
      console.log('🔄 TabbedSidebar: Refreshing itinerary and bookings after purchase')
      loadItinerary();
      loadBookings();
    }
  }, [refreshTrigger]);

  const handleDelete = async (id: string) => {
    if (removingItems.has(id)) return;

    try {
      setRemovingItems(prev => new Set(prev).add(id));
      const success = await deleteItineraryItem(id);
      if (success) {
        setItineraryItems(prev => prev.filter(item => item.id !== id));
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

  const handleItemClick = (location: string | undefined) => {
    if (location) {
      setSelectedLocation(location);
      setSelectedLocations([]);
      setActiveTab('map');
    }
  };

  const handleDayClick = (dayGroups: Record<string, ItineraryItem[]>) => {
    // Flatten all items from all time periods in the day, sorted by time_of_day
    const allItems = Object.entries(dayGroups)
      .sort(([timeA], [timeB]) => getTimeOfDayOrder(timeA) - getTimeOfDayOrder(timeB))
      .flatMap(([_, items]) => items);

    const locations = allItems
      .map(item => item.location)
      .filter((loc): loc is string => !!loc);

    if (locations.length > 0) {
      setSelectedLocations(locations);
      setSelectedLocation('');
      setActiveTab('map');
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

  const ItineraryCard = ({ item, showType = true }: { item: ItineraryItem; showType?: boolean }) => (
    <div 
      className="bg-gray-50 rounded-lg p-3 border border-gray-100 hover:border-gray-200 transition-all cursor-pointer"
      onClick={() => handleItemClick(item.location)}
    >
      <div className="flex items-start gap-3">
        <div className="text-xl w-8 h-8 flex items-center justify-center bg-white rounded-lg border border-gray-100">
          {getIcon(item.type)}
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
          title="Remove from itinerary"
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
      
      {item.location && (
        <div className="flex items-center gap-1.5 text-sm text-gray-500 mt-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
          </svg>
          {item.location}
        </div>
      )}
      
      {(item.details || item.description) && (
        <p className="text-sm text-gray-600 mt-2 line-clamp-2">{item.details || item.description}</p>
      )}
      
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        {item.date && (
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
            {item.date}
          </div>
        )}
        {item.price && (
          <div className="text-sm font-semibold text-[#1668e3]">{item.price}</div>
        )}
      </div>
    </div>
  );

  return (
    <div className="w-1/2 flex flex-col bg-white m-3 ml-0 rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      {/* Tab Navigation */}
      <div className="flex gap-4 px-4 py-2 bg-[#f0f4ff] border-b border-gray-200 overflow-x-auto">
        <TabButton tab="itinerary" label="All" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
          </svg>
        } />
        <TabButton tab="hotels" label="Hotels" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9L12 2L21 9V20C21 21.1 20.1 22 19 22H5C3.9 22 3 21.1 3 20V9Z"/>
            <path d="M9 22V12H15V22"/>
          </svg>
        } />
        <TabButton tab="flights" label="Flights" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M21 16V14L13 9V3.5C13 2.67 12.33 2 11.5 2C10.67 2 10 2.67 10 3.5V9L2 14V16L10 13.5V19L8 20.5V22L11.5 21L15 22V20.5L13 19V13.5L21 16Z"/>
          </svg>
        } />
        <TabButton tab="map" label="Map" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
          </svg>
        } />
        <TabButton tab="bookings" label="Bookings" icon={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
          </svg>
        } />
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'itinerary' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">📋 Complete Itinerary</h3>
              <button 
                onClick={loadItinerary}
                disabled={loading}
                className="p-2 text-gray-500 hover:text-[#1668e3] hover:bg-gray-100 rounded-lg transition-colors"
                title="Refresh"
              >
                {loading ? '⟳' : '↻'}
              </button>
            </div>
            {loading ? (
              <p className="text-gray-500 text-center py-8">Loading...</p>
            ) : itineraryItems.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No itinerary items yet. Ask the agent to plan your trip!</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(groupedItems).map(([day, timeGroups]) => {
                  const isCollapsed = collapsedDays.has(day);

                  // Count total items and locations across all time periods
                  const allItemsInDay = Object.values(timeGroups).flat();
                  const locationsCount = allItemsInDay.filter(item => item.location).length;
                  const totalItems = allItemsInDay.length;

                  // Sort time periods: morning, afternoon, evening
                  const sortedTimeGroups = Object.entries(timeGroups)
                    .sort(([timeA], [timeB]) => getTimeOfDayOrder(timeA) - getTimeOfDayOrder(timeB));

                  return (
                    <div key={day}>
                      <div className="flex items-center gap-2 w-full mb-2">
                        <button
                          className="text-xs text-gray-400 hover:text-gray-600"
                          onClick={() => setCollapsedDays(prev => {
                            const newSet = new Set(prev);
                            if (newSet.has(day)) newSet.delete(day);
                            else newSet.add(day);
                            return newSet;
                          })}
                        >
                          {isCollapsed ? '▶' : '▼'}
                        </button>
                        <button
                          className="flex items-center gap-2 flex-1 text-left hover:bg-gray-50 rounded px-2 py-1 transition-colors"
                          onClick={() => handleDayClick(timeGroups)}
                          title={`Show all ${locationsCount} location${locationsCount !== 1 ? 's' : ''} on map`}
                        >
                          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">{day}</div>
                          <div className="flex-1 h-px bg-gray-200"></div>
                          <span className="text-xs text-gray-400">{totalItems} item{totalItems !== 1 ? 's' : ''}</span>
                          {locationsCount > 0 && (
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="text-blue-500">
                              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                            </svg>
                          )}
                        </button>
                      </div>
                      {!isCollapsed && (
                        <div className="space-y-3 ml-2 pl-2 border-l-2 border-gray-100">
                          {sortedTimeGroups.map(([timeOfDay, items]) => (
                            <div key={`${day}-${timeOfDay}`} className="space-y-2">
                              <div className="text-xs font-medium text-gray-600 px-2">
                                {timeOfDay !== 'unscheduled' ? getTimeOfDayLabel(timeOfDay) : '⏰ Unscheduled'}
                              </div>
                              <div className="space-y-2">
                                {items.map(item => <ItineraryCard key={item.id} item={item} />)}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'hotels' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">🏨 Hotels</h3>
              <button 
                onClick={loadItinerary}
                disabled={loading}
                className="p-2 text-gray-500 hover:text-[#1668e3] hover:bg-gray-100 rounded-lg transition-colors"
              >
                {loading ? '⟳' : '↻'}
              </button>
            </div>
            {loading ? (
              <p className="text-gray-500 text-center py-8">Loading...</p>
            ) : hotelItems.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No hotels yet. Ask the agent to find accommodations!</p>
            ) : (
              <div className="space-y-3">
                {hotelItems.map(item => <ItineraryCard key={item.id} item={item} showType={false} />)}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'flights' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">✈️ Flights</h3>
              <button 
                onClick={loadItinerary}
                disabled={loading}
                className="p-2 text-gray-500 hover:text-[#1668e3] hover:bg-gray-100 rounded-lg transition-colors"
              >
                {loading ? '⟳' : '↻'}
              </button>
            </div>
            {loading ? (
              <p className="text-gray-500 text-center py-8">Loading...</p>
            ) : flightItems.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No flights yet. Ask the agent to find flight options!</p>
            ) : (
              <div className="space-y-3">
                {flightItems.map(item => <ItineraryCard key={item.id} item={item} showType={false} />)}
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'map' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">🗺️ Map</h3>
              {selectedLocations.length > 1 && (
                <span className="text-xs text-gray-500">
                  Showing {selectedLocations.length} locations
                </span>
              )}
            </div>
            {itineraryItems.length === 0 ? (
              <p className="text-gray-500 text-center py-8">Add items to your itinerary to see them on the map</p>
            ) : (
              <div className="rounded-lg overflow-hidden border border-gray-200">
                <iframe
                  width="100%"
                  height="400"
                  style={{ border: 0 }}
                  loading="lazy"
                  src={(() => {
                    const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

                    // Multiple locations - use directions mode with waypoints
                    if (selectedLocations.length > 1) {
                      const origin = encodeURIComponent(selectedLocations[0]);
                      const destination = encodeURIComponent(selectedLocations[selectedLocations.length - 1]);
                      const waypoints = selectedLocations.slice(1, -1).map(loc => encodeURIComponent(loc)).join('|');
                      return waypoints
                        ? `https://www.google.com/maps/embed/v1/directions?key=${apiKey}&origin=${origin}&destination=${destination}&waypoints=${waypoints}&mode=walking`
                        : `https://www.google.com/maps/embed/v1/directions?key=${apiKey}&origin=${origin}&destination=${destination}&mode=walking`;
                    }

                    // Single location
                    const location = selectedLocation || itineraryItems[0]?.location || 'World';
                    return `https://www.google.com/maps/embed/v1/place?key=${apiKey}&q=${encodeURIComponent(location)}`;
                  })()}
                  title="Itinerary Map"
                />
              </div>
            )}
            {selectedLocations.length > 0 && (
              <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                <div className="text-xs font-medium text-blue-900 mb-2">Day Locations:</div>
                <div className="space-y-1">
                  {selectedLocations.map((loc, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs text-blue-700">
                      <span className="font-semibold">{idx + 1}.</span>
                      <span>{loc}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'bookings' && (
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">📅 Your Bookings</h3>
            {bookings.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No bookings yet. Complete a purchase to see your bookings here!</p>
            ) : (
              <div className="space-y-3">
                {bookings.map((booking) => (
                  <div key={booking.id} className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                    <div className="flex items-start gap-3">
                      <div className="text-2xl">{getIcon(booking.item_type)}</div>
                      <div className="flex-1">
                        <div className="font-semibold text-gray-900">{booking.title}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {booking.item_type === 'flight' && booking.origin && booking.destination && (
                            <span>{booking.origin} → {booking.destination}</span>
                          )}
                          {booking.item_type === 'hotel' && booking.city_code && (
                            <span>{booking.city_code}</span>
                          )}
                          {booking.departure_date && <span> • {booking.departure_date}</span>}
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
