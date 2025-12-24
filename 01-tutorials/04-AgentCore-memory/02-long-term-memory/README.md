# AgentCore Memory: Long-Term Memory Strategies

## Overview

Long-term memory in Amazon Bedrock AgentCore enables AI agents to maintain persistent information across multiple conversations and sessions. Unlike short-term memory that focuses on immediate context, long-term memory extracts, processes, and stores meaningful information that can be retrieved and applied in future interactions, creating truly personalized and intelligent agent experiences.

## What is Long-Term Memory?

Long-term memory provides:

- **Cross-Session Persistence**: Information that survives beyond individual conversations
- **Intelligent Extraction**: Automatic identification and storage of important facts, preferences, and patterns
- **Semantic Understanding**: Vector-based storage that enables natural language retrieval
- **Personalization**: User-specific information that enables tailored experiences
- **Knowledge Accumulation**: Continuous learning and information building over time

## How Long-Term Memory Strategies Work

Long-term memory operates through **Memory Strategies** that define what information to extract and how to process it. The system works automatically in the background:

### Processing Pipeline

1. **Conversation Analysis**: Saved conversations are analyzed based on configured strategies
2. **Information Extraction**: Important data (facts, preferences, summaries) is extracted using AI models
3. **Structured Storage**: Extracted information is organized in namespaces for efficient retrieval
4. **Semantic Indexing**: Information is vectorized for natural language search capabilities
5. **Consolidation**: Similar information is merged and refined over time

**Processing Time**: Typically takes ~1 minute after conversations are saved, with no additional code required.

### Behind the Scenes

- **AI-Powered Extraction**: Uses foundation models to understand and extract relevant information
- **Vector Embeddings**: Creates semantic representations for similarity-based retrieval
- **Namespace Organization**: Structures information using configurable path-like hierarchies
- **Automatic Consolidation**: Merges and refines similar information to prevent duplication
- **Incremental Learning**: Continuously improves extraction quality based on conversation patterns

## Long-Term Memory Strategy Types

AgentCore Memory supports four distinct strategy types for long-term information storage:

### 1. Semantic Memory Strategy

Stores factual information extracted from conversations using vector embeddings for similarity search.

```python
{
    "semanticMemoryStrategy": {
        "name": "FactExtractor",
        "description": "Extracts and stores factual information",
        "namespaces": ["support/user/{actorId}/facts"]
    }
}
```

**Best for**: Storing product information, technical details, or any factual data that needs to be retrieved through natural language queries.

### 2. Summary Memory Strategy

Creates and maintains summaries of conversations to preserve context for long interactions.

```python
{
    "summaryMemoryStrategy": {
        "name": "ConversationSummary",
        "description": "Maintains conversation summaries",
        "namespaces": ["support/summaries/{sessionId}"]
    }
}
```

**Best for**: Providing context in follow-up conversations and maintaining continuity across long interactions.

### 3. User Preference Memory Strategy

Tracks user-specific preferences and settings to personalize interactions.

```python
{
    "userPreferenceMemoryStrategy": {
        "name": "UserPreferences",
        "description": "Captures user preferences and settings",
        "namespaces": ["support/user/{actorId}/preferences"]
    }
}
```

**Best for**: Storing communication preferences, product preferences, or any user-specific settings.

### 4. Custom Memory Strategy

Allows customization of prompts for extraction and consolidation, providing flexibility for specialized use cases.

```python
{
    "customMemoryStrategy": {
        "name": "CustomExtractor",
        "description": "Custom memory extraction logic",
        "namespaces": ["user/custom/{actorId}"],
        "configuration": {
            "semanticOverride": { # You can also override Summary or User Preferences.
                "extraction": {
                    "appendToPrompt": "Extract specific information based on custom criteria",
                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                },
                "consolidation": {
                    "appendToPrompt": "Consolidate extracted information in a specific format",
                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                }
            }
        }
    }
}
```

**Best for**: Specialized extraction needs that don't fit the standard strategies.

## Understanding Namespaces

Namespaces organize memory records within strategies using a path-like structure. They can include variables that are dynamically replaced:

- `support/facts/{sessionId}`: Organizes facts by session
- `user/{actorId}/preferences`: Stores user preferences by actor ID
- `meetings/{memoryId}/summaries/{sessionId}`: Groups summaries by memory

The `{actorId}`, `{sessionId}`, and `{memoryId}` variables are automatically replaced with actual values when storing and retrieving memories.

## Example: How It Works in Practice

Let's say a user tells your customer support agent: _"I'm vegetarian and I really enjoy Italian cuisine. Please don't call me after 6 PM."_

After you save this conversation, the configured strategies automatically:

**Semantic Strategy** extracts:

- "User is vegetarian"
- "User enjoys Italian cuisine"

**User Preference Strategy** captures:

- "Dietary preference: vegetarian"
- "Cuisine preference: Italian"
- "Contact preference: no calls after 6 PM"

**Summary Strategy** creates:

- "User discussed dietary restrictions and contact preferences"

All of this happens automatically in the background - you only need to save the conversation and the strategies handle the rest.

## Available Sample Notebooks

Explore these hands-on examples to learn long-term memory strategy implementation:

| Integration Method        | Use Case            | Description                                                                             | Notebook                                                                                                       | Architecture                                                                               |
| ------------------------- | ------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Strands Agent Hooks       | Customer Support    | Complete support system with semantic and preference memory strategies                  | [customer-support.ipynb](./01-single-agent/using-strands-agent-hooks/customer-support/customer-support.ipynb)  | [View](./01-single-agent/using-strands-agent-hooks/customer-support/architecture.png)      |
| Strands Agent Hooks       | Math Assistant      | Math tutor assistant that remembers user learning preferences and progress              | [math-assistant.ipynb](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb) | [View](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/architecture.png) |
| LangGraph Agent Hooks     | Nutrition Assistant | Nutrition advisor that saves user dietary preferences and health goals for personalized recommendations | [nutrition-assistant-with-user-preference-saving.ipynb](./01-single-agent/using-langgraph-agent-hooks/nutrition-assistant-with-user-preference-saving.ipynb) | [View](./01-single-agent/using-langgraph-agent-hooks/architecture.png) |
| Strands Agent Memory Tool | Culinary Assistant  | Food recommendation agent that learns dietary preferences and cooking styles            | [culinary-assistant.ipynb](./01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb)         | [View](./01-single-agent/using-strands-agent-memory-tool/architecture.png)                 |
| Multi-Agent               | Agent Collaboration | Travel Assistant with multiple agents sharing and utilizing long-term memory strategies | [travel-booking-assistant.ipynb](./02-multi-agent/with-strands-agent/travel-booking-assistant.ipynb)           | [View](./02-multi-agent/with-strands-agent/architecture.png)                               |

## Getting Started

1. Choose a sample that matches your use case
2. Navigate to the sample folder
3. Install requirements: `pip install -r requirements.txt`
4. Open the Jupyter notebook and follow the step-by-step implementation

## Best Practices

1. **Strategy Selection**: Choose appropriate strategies based on your use case requirements
2. **Namespace Design**: Plan namespace hierarchies for efficient information organization
3. **Extraction Tuning**: Customize extraction prompts for domain-specific information
4. **Performance Monitoring**: Track memory extraction quality and retrieval performance
5. **Privacy Considerations**: Implement appropriate data retention and privacy policies

## Next Steps

After mastering long-term memory strategies, explore:

- Combining short-term and long-term memory for comprehensive agent experiences
- Advanced custom strategy configurations
- Multi-agent memory sharing patterns
- Production deployment considerations
