import { type ClientSchema, a, defineData } from '@aws-amplify/backend'

const schema = a.schema({
  // Simplified User table - minimal data since we use Cognito attributes for user info
  User: a.model({
    id: a.string().required(),       // Cognito user ID (sub) - Primary key only
    sessions: a.hasMany('ChatSession', 'userId'), // Relationship to chat sessions
    feedback: a.hasMany('Feedback', 'userId'),    // Relationship to feedback
    profiles: a.hasMany('UserProfile', 'userId'), // Relationship to user profiles
    createdAt: a.datetime(),         // Creation timestamp
    updatedAt: a.datetime(),         // Last update timestamp
  })
  .authorization((allow: any) => [allow.owner()]),

  // Chat Session model - replaces Bedrock memory sessions
  ChatSession: a.model({
    id: a.id().required(),           // Session ID
    userId: a.id().required(),       // User who owns the session
    user: a.belongsTo('User', 'userId'), // Relationship to user
    title: a.string(),               // Session title/topic
    messages: a.hasMany('ChatMessage', 'sessionId'), // Relationship to messages
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Chat Message model - replaces Bedrock memory messages
  ChatMessage: a.model({
    id: a.id().required(),
    sessionId: a.id().required(),    // Foreign key to ChatSession
    session: a.belongsTo('ChatSession', 'sessionId'), // Relationship to session
    role: a.enum(['user', 'assistant']), // Message role
    content: a.string().required(),  // Message content
    timestamp: a.datetime(),         // Message timestamp
    feedback: a.hasMany('Feedback', 'messageId'), // Relationship to feedback
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Feedback model - for message feedback (thumbs up/down)
  Feedback: a.model({
    id: a.id().required(),
    messageId: a.id().required(),    // Foreign key to ChatMessage
    message: a.belongsTo('ChatMessage', 'messageId'), // Relationship to message
    userId: a.id().required(),       // User who gave feedback
    user: a.belongsTo('User', 'userId'), // Relationship to user
    feedback: a.enum(['up', 'down']), // Feedback type
    comment: a.string(),             // Optional comment
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Wishlist model - for cart functionality with multiple items per user
  Wishlist: a.model({
    id: a.id().required(),           // AppSync auto-generated UUID (Primary Key)
    user_id: a.string().required(),  // User identifier (attribute)
    asin: a.string(),                // Amazon Standard Identification Number (optional for hotels/flights)
    item_type: a.string(),           // 'product', 'hotel', or 'flight'
    title: a.string().required(),    // Product/Hotel/Flight title
    price: a.string().required(),    // Product/Hotel/Flight price
    reviews: a.string(),             // Product review score
    url: a.string(),                 // Product URL
    // Hotel-specific fields
    hotel_id: a.string(),            // Amadeus hotel ID
    city_code: a.string(),           // City code (e.g., 'NYC', 'PAR')
    rating: a.string(),              // Hotel rating
    amenities: a.string(),           // Comma-separated amenities
    // Flight-specific fields
    flight_id: a.string(),           // Amadeus flight offer ID
    origin: a.string(),              // Origin airport code
    destination: a.string(),         // Destination airport code
    departure_date: a.string(),      // Departure date (YYYY-MM-DD)
    airline: a.string(),             // Airline name/code
    // Note: createdAt and updatedAt are automatically added by Amplify
  })
  // Uses default id as primary key - no custom identifier needed
  .authorization((allow: any) => [allow.authenticated()])
  .secondaryIndexes((index: any) => [
    index('user_id')  // GSI for fast user queries
  ]),

  // UserProfile model - for user preferences and onboarding
  UserProfile: a.model({
    id: a.id().required(),
    userId: a.id().required(),       // Cognito user ID
    user: a.belongsTo('User', 'userId'), // Relationship to user
    name: a.string(),                // Display name
    email: a.string(),               // Email address
    address: a.string(),             // User address
    notes: a.string(),               // Free text notes
    onboardingCompleted: a.boolean().default(false), // Onboarding status
    preferences: a.json(),           // User preferences as JSON
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Itinerary model - for travel itinerary items
  Itinerary: a.model({
    id: a.id().required(),           // AppSync auto-generated UUID
    user_id: a.string().required(),  // User identifier
    type: a.string().required(),     // 'flight', 'hotel', 'activity', 'restaurant', 'transport'
    title: a.string().required(),    // Item title
    location: a.string(),            // Location/destination
    price: a.string(),               // Price
    date: a.string(),                // Date (YYYY-MM-DD)
    time_of_day: a.string(),         // Time of day: 'morning', 'afternoon', 'evening'
    day: a.string(),                 // Day number in itinerary
    details: a.string(),             // Additional details
    description: a.string(),         // Event description
  })
  .authorization((allow) => [allow.authenticated()])
  .secondaryIndexes((index) => [
    index('user_id')  // GSI for fast user queries
  ]),

  // Bookings model - for completed purchases
  Bookings: a.model({
    id: a.id().required(),           // AppSync auto-generated UUID
    user_id: a.string().required(),  // User identifier
    order_id: a.string().required(), // Order ID from purchase
    item_type: a.string().required(),// 'flight', 'hotel', 'product'
    title: a.string().required(),    // Item title
    price: a.string().required(),    // Price paid
    purchase_date: a.string(),       // Purchase date (ISO string)
    // Flight-specific fields
    flight_id: a.string(),
    origin: a.string(),
    destination: a.string(),
    departure_date: a.string(),
    airline: a.string(),
    // Hotel-specific fields
    hotel_id: a.string(),
    city_code: a.string(),
    rating: a.string(),
    amenities: a.string(),
    // Product-specific fields
    asin: a.string(),
    url: a.string(),
  })
  .authorization((allow) => [allow.authenticated()])
  .secondaryIndexes((index) => [
    index('user_id'),
    index('order_id')
  ]),

})

export type Schema = ClientSchema<typeof schema>

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
})
