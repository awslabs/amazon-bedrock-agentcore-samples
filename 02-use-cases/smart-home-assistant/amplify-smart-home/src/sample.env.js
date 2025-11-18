// ================================
// APPLICATION INFORMATION
// ================================

import { v4 as uuidv4 } from "uuid";

// Main application name displayed in UI
const APP_NAME = "Smart Home";

// Default section to load when accessing the home route
const DEFAULT_HOME_SECTION = "smart-home-assistant";

// ================================
// SECTIONS CONFIGURATION
// ================================

/**
 * Configuration for different application sections/assistants
 * Each section can have its own database, agent, and application settings
 * This allows for multi-tenant or multi-assistant deployments
 */
const SECTIONS_CONFIG = {
  "smart-home-assistant": {
    // Assistant Configuration
    title: "Smart Home Assistant",                    // Display name in navigation
    url: "/smart-home-assistant",                     // Route URL for this section
    iconName: "SmartToyIcon",                     // Material-UI icon name (not component)
    assistantName: "Smart Home Assistant", // Assistant display name
    assistantIcon: "/images/amazon-bedrock-agentcore.png", // Assistant avatar image

    // Assistant Description
    assistantDescription:
      "Control and automate your intelligent house devices, monitor systems, and analyze camera feeds with intelligent assistance",

    // Sample Questions for Welcome Screen
    sampleQuestions: [
      { question: "What's the busiest day in my backyard this month?", color: "#F4D556" },
      { question: "Can you generate a clip from yesterday between 8:09-8:11?", color: "#EC734A" },
      { question: "What unusual activity has been detected in the backyard over the last 7 days?", color: "#4caf50" },
      { question: "What is the weather and temperature?", color: "#EC6786" }
    ],

    // Session Configuration
    sessionId: uuidv4(), // Unique session ID for this assistant

    // Database Configuration
    database: {
      tableName: "", // DynamoDB table for media assets - To Update
    },

    // Amazon Bedrock AgentCore Configuration
    agent: {
      runtimeArn: "", // AgentCore runtime ARN - To Update
      endpointName: "DEFAULT",                    // Agent endpoint name - To Update
      //memoryTurns: 10,                           // Number of conversation turns to keep in memory
    },

  },
};

// ================================
// SYSTEM CONFIGURATION
// ================================

// Maximum length for search input queries (characters)
const MAX_LENGTH_INPUT_SEARCH = 140;

// ================================
// EXPORTS
// ================================

export {
  // System Configuration
  MAX_LENGTH_INPUT_SEARCH,

  // Application Information
  APP_NAME,

  // Navigation & Sections Configuration
  SECTIONS_CONFIG,
  DEFAULT_HOME_SECTION,
};