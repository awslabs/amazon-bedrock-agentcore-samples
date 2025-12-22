export interface ItineraryItem {
  id: string;
  type: 'flight' | 'hotel' | 'activity' | 'restaurant' | 'transport';
  title: string;
  date?: string;
  time?: string;
  location?: string;
  price?: string;
  details?: string;
  icon?: string;
}

const cleanText = (text: string): string => {
  return text
    .replace(/[*_~`]/g, '') // Remove markdown
    .replace(/\s+/g, ' ') // Normalize spaces
    .trim();
};

const isValidItem = (title: string): boolean => {
  if (!title || title.length < 3) return false;
  // Check if it's mostly complete words (not fragments)
  const words = title.split(/\s+/);
  if (words.length === 1 && words[0].length < 3) return false;
  return true;
};

export const parseItineraryFromMessage = (content: string): ItineraryItem[] => {
  const items: ItineraryItem[] = [];
  
  // Only parse if content has clear markers
  const lines = content.split('\n');
  
  for (const line of lines) {
    const cleanLine = cleanText(line);
    
    // Flight: Look for airport codes
    const flightMatch = cleanLine.match(/([A-Z]{3})\s*(?:to|→|-|–)\s*([A-Z]{3})/);
    if (flightMatch && (cleanLine.includes('✈️') || cleanLine.toLowerCase().includes('flight'))) {
      items.push({
        id: `flight-${Date.now()}-${Math.random()}`,
        type: 'flight',
        title: `${flightMatch[1]} → ${flightMatch[2]}`,
        location: `${flightMatch[1]} to ${flightMatch[2]}`,
        icon: '✈️'
      });
      continue;
    }
    
    // Hotel: Look for hotel emoji or word
    if (cleanLine.includes('🏨') || cleanLine.toLowerCase().includes('hotel:')) {
      const titleMatch = cleanLine.match(/(?:🏨|hotel:)\s*(.+?)(?:\s+in\s+|\s*$)/i);
      if (titleMatch && isValidItem(titleMatch[1])) {
        items.push({
          id: `hotel-${Date.now()}-${Math.random()}`,
          type: 'hotel',
          title: cleanText(titleMatch[1]),
          icon: '🏨'
        });
        continue;
      }
    }
    
    // Activity: Look for activity emoji or word
    if (cleanLine.match(/🎭|🎨|🏛️|activity:|tour:/i)) {
      const titleMatch = cleanLine.match(/(?:🎭|🎨|🏛️|activity:|tour:)\s*(.+?)(?:\s*$)/i);
      if (titleMatch && isValidItem(titleMatch[1])) {
        items.push({
          id: `activity-${Date.now()}-${Math.random()}`,
          type: 'activity',
          title: cleanText(titleMatch[1]),
          icon: '🎭'
        });
        continue;
      }
    }
    
    // Restaurant: Look for restaurant emoji or word
    if (cleanLine.match(/🍽️|restaurant:|dining:/i)) {
      const titleMatch = cleanLine.match(/(?:🍽️|restaurant:|dining:)\s*(.+?)(?:\s*$)/i);
      if (titleMatch && isValidItem(titleMatch[1])) {
        items.push({
          id: `restaurant-${Date.now()}-${Math.random()}`,
          type: 'restaurant',
          title: cleanText(titleMatch[1]),
          icon: '🍽️'
        });
        continue;
      }
    }
  }
  
  return items;
};

export const extractItineraryFromMessages = (messages: any[]): ItineraryItem[] => {
  const allItems: ItineraryItem[] = [];
  
  messages.forEach(message => {
    if (message.role === 'assistant' && message.content) {
      const items = parseItineraryFromMessage(message.content);
      allItems.push(...items);
    }
  });
  
  // Deduplicate by title
  const seen = new Set<string>();
  return allItems.filter(item => {
    const key = item.title.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};
