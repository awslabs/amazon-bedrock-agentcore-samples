# Agent Capabilities Guide - Shopping Focus

## Overview

The Concierge Agent system consists of three specialized agents working together to provide comprehensive shopping assistance and purchase management:

1. **Supervisor Agent** - Main orchestrator that coordinates all interactions
2. **Shopping Assistant** - Handles product search and recommendations
3. **Cart Manager** - Manages shopping cart, payments, and purchase flow

---

## 🎯 Supervisor Agent

### Role
The Supervisor Agent is the main entry point for all user interactions. It orchestrates conversations and delegates tasks to specialized agents via the AgentCore Gateway.

### Core Capabilities

#### 1. Conversation Orchestration
- Routes user requests to appropriate specialized agents
- Maintains conversation context and memory across sessions
- Formats and presents responses from sub-agents to users
- Handles multi-turn conversations with context awareness

#### 2. Gateway Communication
- Communicates with specialized agents via AgentCore Gateway
- Passes user context (user_id, session_id) to all sub-agents
- Handles streaming responses from sub-agents
- Manages tool invocations across distributed services

### How It Works Together
1. User sends message to Supervisor
2. Supervisor analyzes intent and routes to appropriate agent via Gateway
3. Specialized agent processes request and returns results
4. Supervisor formats response and presents to user

---

## 🛍️ Shopping Assistant

### Role
The Shopping Assistant specializes in product discovery, recommendations, and packing list generation. It helps users find products and organize their shopping needs.

### Tools & Capabilities

#### 1. Product Search
**`single_productsearch(user_id, question)`**
- Searches for products based on user queries
- Integrates with Product Advertising API (PaAPI) for real product data
- Returns product recommendations with ASINs
- Provides detailed product information including prices and reviews

**Use Cases:**
- "Find me wireless headphones under $100"
- "Show me the best running shoes for marathon training"
- "I need a laptop for video editing"
- "What are the top-rated coffee makers?"

**Parameters:**
- `user_id`: User identifier for personalized results
- `question`: Natural language product search query

**Returns:**
```json
{
  "answer": "Here are the top wireless headphones under $100...",
  "asins": ["B08ASIN123", "B08ASIN456", "B08ASIN789"]
}
```

**Current Status:**
> ⚠️ **Note**: Product search requires Product Advertising API (PaAPI) integration. Currently returns placeholder response directing users to use internet search for product research.

#### 2. Packing List Generation
**`generate_packinglist_with_productASINS(user_id, question)`**
- Generates comprehensive packing lists for trips or events
- Recommends specific products for each packing list item
- Returns product ASINs for easy cart addition
- Organizes items by category (clothing, electronics, toiletries, etc.)

**Use Cases:**
- "Create a packing list for a week in Hawaii"
- "What should I pack for a business trip to New York?"
- "I need a camping packing list with product recommendations"
- "Help me pack for a ski vacation"

**Parameters:**
- `user_id`: User identifier for personalized recommendations
- `question`: Natural language packing list request

**Returns:**
```json
{
  "packing_list": {
    "clothing": [
      {"item": "Swimsuit", "asin": "B08SWIM123"},
      {"item": "Sunglasses", "asin": "B08SUN456"}
    ],
    "electronics": [
      {"item": "Phone Charger", "asin": "B08CHRG789"}
    ],
    "toiletries": [
      {"item": "Sunscreen SPF 50", "asin": "B08SUN999"}
    ]
  }
}
```

**Current Status:**
> ⚠️ **Note**: Packing list generation requires Product Advertising API (PaAPI) integration. Currently returns placeholder response.

### Integration with Internet Search

While PaAPI integration is pending, the Shopping Assistant works with the Internet Search agent to provide product research:

**Workflow:**
1. User asks: "Find me the best wireless headphones"
2. Shopping Assistant recognizes product search intent
3. Supervisor routes to Internet Search agent for web research
4. Internet Search returns articles, reviews, and recommendations
5. User can manually add products to cart using product names

### Future Enhancements

When PaAPI is integrated, the Shopping Assistant will:
- Return real product data with prices, ratings, and availability
- Provide direct "Add to Cart" functionality with ASINs
- Show product images and detailed specifications
- Compare prices across different sellers
- Track price history and deal alerts
- Personalize recommendations based on user preferences

---

## 🛒 Cart Manager

### Role
The Cart Manager handles all shopping cart operations, payment processing, and purchase flow. It integrates with Visa for secure payment tokenization and manages the complete checkout experience.

### Tools & Capabilities

#### 1. Cart Viewing
**`get_cart(user_id)`**
- Retrieves all items in user's shopping cart
- Returns products with full details
- Includes pricing, reviews, and product URLs

**Returns:**
```json
[
  {
    "asin": "B09XM5ASIN",
    "title": "Sony WH-1000XM5 Headphones",
    "price": "$399.99",
    "qty": 1,
    "reviews": "4.8/5 (12,450 reviews)",
    "url": "https://amazon.com/..."
  },
  {
    "asin": "B09AIRPODS",
    "title": "Apple AirPods Pro",
    "price": "$249.99",
    "qty": 1,
    "reviews": "4.7/5 (89,234 reviews)"
  }
]
```

#### 2. Adding Items to Cart

**`add_to_cart(user_id, items)`**
- Adds products to shopping cart
- Requires ASIN, title, price
- Optional: reviews, URL for product details
- Supports batch addition of multiple items

**Example:**
```json
[
  {
    "asin": "B09XM5ASIN",
    "title": "Sony WH-1000XM5 Headphones",
    "price": "$399.99",
    "reviews": "4.8/5",
    "url": "https://amazon.com/sony-headphones"
  },
  {
    "asin": "B09AIRPODS",
    "title": "Apple AirPods Pro",
    "price": "$249.99",
    "reviews": "4.7/5"
  }
]
```

#### 3. Removing Items
**`remove_from_cart(user_id, asins)`**
- Removes products from cart by ASIN
- Supports batch removal of multiple items
- Returns count of removed items

**Use Cases:**
- "Remove the Sony headphones from my cart"
- "Delete all items from my cart"
- "Remove the AirPods"

#### 4. Purchase Flow

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
  "total_amount": 649.98,
  "total_items": 2,
  "payment_method": "Visa ending in 1234",
  "items": [
    {"title": "Sony Headphones", "price": 399.99},
    {"title": "Apple AirPods", "price": 249.99}
  ],
  "message": "Ready to purchase 2 items for $649.98..."
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
  "order_id": "ORD-20251126-ABC123",
  "total_amount": 649.98,
  "items_count": 2,
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

#### 5. Payment Card Management

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

### Example: Complete Shopping Flow

**User Request:** "I need wireless headphones and a laptop bag for work"

#### Phase 1: Product Discovery (Supervisor → Shopping Assistant)
1. **Supervisor** receives request and routes to Shopping Assistant via Gateway
2. **Shopping Assistant** executes:
   - `single_productsearch("wireless headphones for work")` - Find headphones
   - `single_productsearch("laptop bag professional")` - Find bags
3. **Shopping Assistant** returns product recommendations with ASINs
4. **Supervisor** presents options to user

#### Phase 2: Adding to Cart (Supervisor → Cart Manager)
5. User says: "Add the Sony headphones and the leather laptop bag"
6. **Supervisor** routes to Cart Manager via Gateway
7. **Cart Manager** executes:
   - `add_to_cart()` - Adds both selected products
8. **Supervisor** confirms items added

#### Phase 3: Cart Review (Supervisor → Cart Manager)
9. User says: "Show me my cart"
10. **Cart Manager** executes:
    - `get_cart()` - Retrieves all cart items
11. **Supervisor** displays cart with totals

#### Phase 4: Purchase (Supervisor → Cart Manager)
12. User says: "I'm ready to checkout"
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
- **Shopping Assistant** → **Supervisor**: Product recommendations with ASINs
- **Supervisor** → **Cart Manager**: Selected items for purchase
- **Cart Manager** → **Supervisor**: Purchase confirmations
- All data flows through Supervisor for consistency

### 3. Error Handling
- Each agent validates inputs and returns structured errors
- Supervisor handles errors gracefully and informs user
- Failed operations don't corrupt cart state
- Retry logic for transient failures

### 4. State Management
- **Shopping Lists**: Stored in DynamoDB via Supervisor
- **Cart**: Stored in DynamoDB via Cart Manager
- **User Profile**: Stored in DynamoDB (payment cards, preferences)
- **Conversation**: Stored in AgentCore Memory

---

## 🎯 Best Practices

### For Shopping Assistance:
1. Use specific product queries for better results
2. Include price ranges and preferences in searches
3. Generate packing lists for trips to get product recommendations
4. Review product details before adding to cart

### For Cart Management:
1. Add items to cart as user selects them
2. Use `request_purchase_confirmation()` before finalizing
3. Always send confirmation email after successful purchase
4. Clear cart only after successful purchase

### For Supervisor Orchestration:
1. Route product searches to Shopping Assistant
2. Route cart operations to Cart Manager
3. Maintain conversation context across agent calls
4. Format sub-agent responses for user-friendly display
5. Handle errors gracefully with helpful messages

---

## 📊 Tool Summary

| Agent | Tool Count | Primary Functions |
|-------|-----------|-------------------|
| **Supervisor** | 0 | Conversation orchestration, routing |
| **Shopping Assistant** | 2 | Product search, packing lists |
| **Cart Manager** | 8 | Cart operations, payments, purchases |

**Total Tools**: 10 specialized tools working together to provide comprehensive shopping assistance.

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
- **Shopping Assistant**: Domain expertise in product discovery
- **Cart Manager**: Domain expertise in commerce and payments
- Each agent focused on its specialty

### Extensibility
- Easy to add new product sources (PaAPI, other APIs)
- Can integrate with multiple payment providers
- Supports various shopping scenarios (retail, events, gifts)
- Flexible architecture for adding new specialized agents

---

## 🔮 Future Enhancements

### Shopping Assistant
- **PaAPI Integration**: Real product data with prices and availability
- **Price Comparison**: Compare prices across multiple sellers
- **Deal Alerts**: Notify users of price drops and sales
- **Personalization**: Learn user preferences over time
- **Visual Search**: Find products by image
- **Reviews Analysis**: Summarize product reviews

### Cart Manager
- **Wishlist Management**: Save items for later
- **Price Tracking**: Monitor cart items for price changes
- **Bundle Deals**: Suggest product bundles for savings
- **Subscription Management**: Handle recurring purchases
- **Gift Options**: Add gift wrapping and messages
- **Multiple Payment Methods**: Support split payments

### Integration
- **Loyalty Programs**: Track and apply rewards points
- **Shipping Options**: Compare delivery methods and costs
- **Order Tracking**: Real-time shipment tracking
- **Returns Management**: Handle returns and exchanges
- **Social Shopping**: Share carts and recommendations

This architecture enables a powerful, scalable, and maintainable shopping assistant system that can handle complex multi-step workflows while maintaining clean separation of responsibilities.
