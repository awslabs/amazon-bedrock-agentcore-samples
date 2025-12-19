# Agent Capabilities Guide

## Overview

The Concierge Agent system consists of three specialized agents working together to provide comprehensive travel planning and shopping assistance:

1. **Supervisor Agent** - Main orchestrator that coordinates all interactions
2. **Travel Assistant** - Handles travel planning, bookings, and destination information
3. **Cart Manager** - Manages shopping cart, payments, and purchase flow

---

## 🎯 Supervisor Agent

### Role
The Supervisor Agent is the main entry point for all user interactions. It orchestrates conversations, delegates tasks to specialized agents via the AgentCore Gateway, and manages the user's itinerary.

### Core Capabilities

#### 1. Conversation Orchestration
- Routes user requests to appropriate specialized agents
- Maintains conversation context and memory across sessions
- Formats and presents responses from sub-agents to users
- Handles multi-turn conversations with context awareness

#### 2. Itinerary Management
The supervisor directly manages the user's travel itinerary with two key tools:

**`save_itinerary(user_id, items)`**
- Saves complete itineraries to DynamoDB
- Accepts JSON array of itinerary items
- Supports multiple item types: flight, hotel, activity, restaurant, transport
- Stores details like title, location, price, date, day, and description
- Used after travel assistant creates a complete trip plan

**Example:**
```json
[
  {
    "type": "flight",
    "title": "JFK to LAX",
    "price": "$350",
    "date": "2025-12-25",
    "day": 1
  },
  {
    "type": "hotel",
    "title": "Marriott Downtown",
    "location": "Los Angeles",
    "price": "$200/night",
    "date": "2025-12-25",
    "day": 1
  },
  {
    "type": "activity",
    "title": "Hollywood Tour",
    "location": "Los Angeles",
    "price": "$45",
    "date": "2025-12-26",
    "day": 2,
    "description": "Guided tour of Hollywood landmarks"
  }
]
```

**`clear_itinerary(user_id)`**
- Removes all itinerary items for a user
- Used when user wants to start fresh or clear saved plans
- Returns count of deleted items

#### 3. Gateway Communication
- Communicates with specialized agents via AgentCore Gateway
- Passes user context (user_id, session_id) to all sub-agents
- Handles streaming responses from sub-agents
- Manages tool invocations across distributed services

### How It Works Together
1. User sends message to Supervisor
2. Supervisor analyzes intent and routes to appropriate agent via Gateway
3. Specialized agent processes request and returns results
4. Supervisor formats response and presents to user
5. If itinerary is created, Supervisor saves it using `save_itinerary`

---

## ✈️ Travel Assistant

### Role
The Travel Assistant specializes in all travel-related queries including destination research, weather information, flight and hotel searches, and local recommendations.

### Tools & Capabilities

#### 1. Weather Information
**`get_weather(query)`**
- Retrieves 5-day weather forecast for any city
- Uses OpenWeather API with fuzzy city matching
- Provides daily forecasts with temperature, conditions, and descriptions
- Handles natural language queries like "What's the weather in Paris?"

**Example Output:**
```
Day 1 (2025-12-25): 45°F, Partly Cloudy - Light clouds with mild temperatures
Day 2 (2025-12-26): 42°F, Rain - Expect rain throughout the day
...
```

#### 2. Internet Search
**`search_tool(query)`**
- Performs web searches using Tavily API
- Returns formatted results with titles, content, and sources
- Useful for destination research, travel tips, and current information
- Provides up to 5 relevant results per query

**Use Cases:**
- "Best restaurants in Tokyo"
- "Things to do in Barcelona"
- "Travel requirements for Italy"

#### 3. Local Places Search
**`google_places_tool(query)`**
- Searches Google Places API for local businesses and attractions
- Returns detailed place information including ratings, addresses, and photos
- Ideal for finding specific venues, restaurants, or attractions
- Provides structured data for easy parsing

**Use Cases:**
- "Coffee shops near Eiffel Tower"
- "Museums in Rome"
- "Hotels in downtown Seattle"

#### 4. Flight Search
**`get_flight_offers_tool(origin, destination, departure_date, adults, max_price, currency)`**
- Searches Amadeus API for flight offers
- Filters by price, number of passengers, and currency
- Returns flight details including airlines, times, and prices
- Supports IATA airport codes (e.g., JFK, LAX, LHR)

**Parameters:**
- `origin`: Departure airport code (e.g., "BOS")
- `destination`: Arrival airport code (e.g., "PAR")
- `departure_date`: Date in YYYY-MM-DD format
- `adults`: Number of passengers (default: 1)
- `max_price`: Maximum price filter (default: 400)
- `currency`: Currency code (default: "USD")

#### 5. Hotel Search
**`get_hotel_data_tool(city_code, ratings, amenities, max_price)`**
- Searches Amadeus API for hotels in a city
- Filters by star rating, amenities, and price
- Returns hotel details including name, location, and pricing
- Supports city codes (e.g., NYC, PAR, ROM)

**Parameters:**
- `city_code`: City code (e.g., "NYC", "PAR")
- `ratings`: Star ratings to filter (e.g., "4,5" for 4-5 stars)
- `amenities`: Required amenities (e.g., "SWIMMING_POOL", "SPA")
- `max_price`: Maximum price per night (default: 500)

### Workflow Example

**User:** "Plan a 3-day trip to Paris in December"

1. **Weather Check**: Travel Assistant uses `get_weather("Paris")` to check conditions
2. **Flight Search**: Uses `get_flight_offers_tool()` to find flights
3. **Hotel Search**: Uses `get_hotel_data_tool("PAR")` to find accommodations
4. **Local Research**: Uses `search_tool()` and `google_places_tool()` for attractions
5. **Itinerary Creation**: Compiles all information into structured itinerary
6. **Handoff to Supervisor**: Returns complete itinerary to Supervisor
7. **Save**: Supervisor calls `save_itinerary()` to persist the plan

---

## 🛒 Cart Manager

### Role
The Cart Manager handles all shopping cart operations, payment processing, and purchase flow. It integrates with Visa for secure payment tokenization and manages the complete checkout experience.

### Tools & Capabilities

#### 1. Cart Viewing
**`get_cart(user_id)`**
- Retrieves all items in user's shopping cart
- Returns products, hotels, and flights with full details
- Groups items by type for easy display
- Includes pricing, dates, and booking information

**Returns:**
```json
[
  {
    "item_type": "hotel",
    "title": "Marriott Downtown",
    "price": "$200",
    "details": {
      "hotel_id": "HLNYC123",
      "city_code": "NYC",
      "rating": "5"
    }
  }
]
```

#### 2. Adding Items to Cart

**`add_to_cart(user_id, items)`**
- Adds general products to cart
- Requires ASIN, title, price, and optional reviews/URL
- Used for shopping items and general purchases

**`add_hotel_to_cart(user_id, hotels)`**
- Adds hotels from Amadeus API to cart
- Stores hotel_id, city_code, rating, and amenities
- Normalizes pricing (removes "/night" suffix)
- Links to travel itinerary

**`add_flight_to_cart(user_id, flights)`**
- Adds flights from Amadeus API to cart
- Stores flight_id, origin, destination, departure_date, airline
- Tracks flight-specific details for booking
- Links to travel itinerary

**Example - Adding Hotel:**
```json
{
  "hotel_id": "HLNYC123",
  "title": "Grand Hotel NYC",
  "price": "$250/night",
  "city_code": "NYC",
  "rating": "5",
  "amenities": "WIFI,POOL,GYM"
}
```

#### 3. Removing Items
**`remove_from_cart(user_id, identifiers, item_type)`**
- Removes items by identifier (ASIN, hotel_id, or flight_id)
- Supports batch removal of multiple items
- Validates item type: 'product', 'hotel', or 'flight'
- Returns count of removed items

#### 4. Date Updates
**`update_itinerary_date(user_id, identifier, item_type, new_date)`**
- Updates departure date for flights or check-in date for hotels
- Validates date format (YYYY-MM-DD)
- Updates all matching items in cart
- Returns success status and count of updated items

**Use Case:**
User wants to change flight from Dec 25 to Dec 27:
```python
update_itinerary_date(
    user_id="user-123",
    identifier="FL123456",
    item_type="flight",
    new_date="2025-12-27"
)
```

#### 5. Purchase Flow

**Step 1: Request Confirmation**
**`request_purchase_confirmation(user_id)`**
- Prepares purchase summary with total amount
- Retrieves user's payment card information
- Calculates total from all cart items
- Returns summary requiring user confirmation

**Returns:**
```json
{
  "requires_confirmation": true,
  "total_amount": 850.00,
  "total_items": 3,
  "payment_method": "Visa ending in 1234",
  "message": "Ready to purchase 3 items for $850.00..."
}
```

**Step 2: Confirm Purchase**
**`confirm_purchase(user_id)`**
- Executes the purchase after user confirms
- Processes payment via Visa tokenization
- Generates unique order ID
- Clears cart after successful purchase
- Returns order confirmation

**Returns:**
```json
{
  "success": true,
  "order_id": "ORD-20251225-ABC123",
  "total_amount": 850.00,
  "items_count": 3,
  "payment_method": "Visa ending in 1234",
  "message": "Purchase completed successfully!"
}
```

**Step 3: Send Confirmation Email**
**`send_purchase_confirmation_email(order_id, recipient_email, total_amount, items_count, payment_method)`**
- Sends purchase confirmation via AWS SES
- Includes order details and receipt
- Professional HTML email template
- Returns message ID for tracking

#### 6. Payment Card Management

**`onboard_card(user_id, card_number, expiration_date, cvv, card_type, is_primary)`**
- Securely onboards new payment card
- Integrates with Visa tokenization
- Stores encrypted token in user profile
- Supports primary and backup cards
- Returns vProvisionedTokenId for future transactions

**Security Features:**
- Card numbers are tokenized via Visa
- Only last 4 digits stored
- CVV never persisted
- Encrypted token used for payments

**`get_visa_iframe_config(user_id)`**
- Provides configuration for Visa iframe integration
- Returns secure iframe URL and settings
- Used by UI for card onboarding flow
- Ensures PCI compliance

---

## 🔄 How Agents Work Together

### Example: Complete Travel Booking Flow

**User Request:** "I want to book a 3-day trip to New York for Christmas"

#### Phase 1: Planning (Supervisor → Travel Assistant)
1. **Supervisor** receives request and routes to Travel Assistant via Gateway
2. **Travel Assistant** executes:
   - `get_weather("New York")` - Check December weather
   - `get_flight_offers_tool("BOS", "NYC", "2025-12-25")` - Find flights
   - `get_hotel_data_tool("NYC", "4,5")` - Find hotels
   - `google_places_tool("attractions in New York")` - Find activities
3. **Travel Assistant** compiles complete 3-day itinerary
4. **Supervisor** receives itinerary and calls `save_itinerary()` to persist

#### Phase 2: Booking (Supervisor → Cart Manager)
5. User says: "Add the Marriott hotel and the morning flight to my cart"
6. **Supervisor** routes to Cart Manager via Gateway
7. **Cart Manager** executes:
   - `add_hotel_to_cart()` - Adds selected hotel
   - `add_flight_to_cart()` - Adds selected flight
8. **Supervisor** confirms items added

#### Phase 3: Modification (Supervisor → Cart Manager)
9. User says: "Actually, change the flight to December 26th"
10. **Cart Manager** executes:
    - `update_itinerary_date("FL123", "flight", "2025-12-26")`
11. **Supervisor** confirms date updated

#### Phase 4: Purchase (Supervisor → Cart Manager)
12. User says: "I'm ready to purchase"
13. **Cart Manager** executes:
    - `request_purchase_confirmation()` - Shows summary
14. **Supervisor** presents summary to user
15. User confirms purchase
16. **Cart Manager** executes:
    - `confirm_purchase()` - Processes payment
    - `send_purchase_confirmation_email()` - Sends receipt
17. **Supervisor** confirms successful purchase

---

## 🔑 Key Integration Points

### 1. User Context Flow
- **Supervisor** maintains user_id and session_id
- All tool calls include user_id for personalization
- Session context preserved across agent boundaries
- Memory shared via AgentCore Memory service

### 2. Data Handoffs
- **Travel Assistant** → **Supervisor**: Structured itinerary data
- **Supervisor** → **Cart Manager**: Selected items for booking
- **Cart Manager** → **Supervisor**: Purchase confirmations
- All data flows through Supervisor for consistency

### 3. Error Handling
- Each agent validates inputs and returns structured errors
- Supervisor handles errors gracefully and informs user
- Failed operations don't corrupt cart or itinerary state
- Retry logic for transient failures

### 4. State Management
- **Itinerary**: Stored in DynamoDB via Supervisor
- **Cart**: Stored in DynamoDB via Cart Manager
- **User Profile**: Stored in DynamoDB (payment cards, preferences)
- **Conversation**: Stored in AgentCore Memory

---

## 🎯 Best Practices

### For Travel Planning:
1. Always check weather before suggesting dates
2. Search flights and hotels together for better coordination
3. Use `google_places_tool` for specific venue recommendations
4. Save complete itineraries with `save_itinerary()` after planning
5. Include descriptions in itinerary items for context

### For Cart Management:
1. Add items to cart as user selects them
2. Use `request_purchase_confirmation()` before finalizing
3. Always send confirmation email after successful purchase
4. Handle date changes with `update_itinerary_date()`
5. Clear cart only after successful purchase

### For Supervisor Orchestration:
1. Route requests to appropriate specialized agent
2. Maintain conversation context across agent calls
3. Format sub-agent responses for user-friendly display
4. Save important data (itineraries) immediately
5. Handle errors gracefully with helpful messages

---

## 📊 Tool Summary

| Agent | Tool Count | Primary Functions |
|-------|-----------|-------------------|
| **Supervisor** | 2 | Itinerary management, orchestration |
| **Travel Assistant** | 5 | Search, weather, flights, hotels, places |
| **Cart Manager** | 11 | Cart operations, payments, purchases |

**Total Tools**: 18 specialized tools working together to provide comprehensive travel and shopping assistance.

---

## 🚀 Architecture Benefits

### Microservices Design
- Each agent is independently deployable
- Agents scale based on demand
- Failures isolated to specific services
- Easy to add new specialized agents

### Gateway Communication
- Centralized routing and authentication
- Consistent API across all agents
- Built-in monitoring and tracing
- Secure inter-agent communication

### Separation of Concerns
- **Supervisor**: Conversation and coordination
- **Travel Assistant**: Domain expertise in travel
- **Cart Manager**: Domain expertise in commerce
- Each agent focused on its specialty

This architecture enables a powerful, scalable, and maintainable travel concierge system that can handle complex multi-step workflows while maintaining clean separation of responsibilities.
