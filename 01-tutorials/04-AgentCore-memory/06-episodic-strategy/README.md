# AgentCore Memory: Episodic Memory Strategy

| Information         | Details                                                      |
|:--------------------|:-------------------------------------------------------------|
| Tutorial type       | Long term Episodic                                           |
| Agent type          | Code Debugging Assistant                                      |
| Agentic Framework   | Strands Agents                                               |
| LLM model           | Anthropic Claude Haiku 4.5                                   |
| Tutorial components | AgentCore Episodic Memory with Reflections, Hooks            |
| Example complexity  | Intermediate                                                 |

## Overview

Episodic memory captures meaningful slices of user and system interactions so applications can recall context in a way that feels focused and relevant. Instead of storing every raw event, it identifies important moments, summarizes them into compact records, and organizes them so the system can retrieve what matters without noise.

**Reflections** build on episodic records by analyzing past episodes to surface insights, patterns, and higher-level conclusions. They turn raw experience into guidance the application can use immediately.

## What is Episodic Memory?

Episodic memory provides:

- **Episode Detection**: Automatically identifies when meaningful interaction sequences complete
- **Structured Capture**: Records situation, intent, assessment, justification, and episode-level reflection
- **Cross-Episode Learning**: Generates reflections that identify patterns across multiple episodes
- **Contextual Retrieval**: Enables agents to learn from past experiences and avoid repeating mistakes

## How Episodic Memory Differs from Other Strategies

| Strategy | Focus | Best For |
|----------|-------|----------|
| **Semantic** | Facts and knowledge | Static information retrieval |
| **User Preference** | User settings and preferences | Personalization |
| **Summary** | Conversation condensation | Long conversation context |
| **Episodic** | Interaction sequences + reflections | Learning from experience |

Episodic memory is unique because it:
1. Captures the **sequence** of actions, not just facts
2. Generates **reflections** that identify patterns across episodes
3. Helps agents understand **why** certain approaches worked or failed

## When to Use Episodic Memory

Ideal use cases include:

- **Customer support conversations**: Learn from successful resolution patterns
- **Agent-driven workflows**: Remember which tool combinations work best
- **Code assistants**: Track debugging approaches that resolved issues
- **Troubleshooting flows**: Identify common failure modes and solutions
- **Personal productivity tools**: Adapt to user working patterns over time

## Strategy Steps

The episodic memory strategy includes three steps:

1. **Extraction**: Analyzes in-progress episode and determines if complete
2. **Consolidation**: Combines extractions into a single episode when complete
3. **Reflection**: Generates insights across multiple episodes

## Namespace Organization

Episodes and reflections are stored in configurable namespaces:

```python
# Store episodes at actor level (recommended for most use cases)
"namespaces": ["workflow/actor/{actorId}/episodes"]

# Reflections must be same as or prefix of episodic namespace
"reflectionConfiguration": {
    "namespaces": ["workflow/actor/{actorId}"]  # Prefix of episodes namespace
}
```

**Important**: The reflection namespace must be the same as or a prefix of the episodic namespace. For example, if episodes are at `debug/actor/{actorId}/episodes`, reflections should be at `debug/actor/{actorId}` (prefix).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Code Debugging Assistant                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │   Developer  │     │              Strands Agent                        │  │
│  │              │────▶│  ┌─────────────────────────────────────────────┐  │  │
│  │  "KeyError   │     │  │           System Prompt                     │  │  │
│  │   in my      │     │  │  "You are an expert debugging assistant..." │  │  │
│  │   code..."   │     │  └─────────────────────────────────────────────┘  │  │
│  └──────────────┘     │                      │                            │  │
│                       │                      ▼                            │  │
│                       │  ┌─────────────────────────────────────────────┐  │  │
│                       │  │         EpisodicMemoryHooks                 │  │  │
│                       │  │  ┌───────────────┐  ┌───────────────────┐   │  │  │
│                       │  │  │ MessageAdded  │  │ AfterInvocation   │   │  │  │
│                       │  │  │    Hook       │  │      Hook         │   │  │  │
│                       │  │  │ (retrieve)    │  │ (save events)     │   │  │  │
│                       │  │  └───────┬───────┘  └─────────┬─────────┘   │  │  │
│                       │  └──────────┼────────────────────┼─────────────┘  │  │
│                       │             │                    │                │  │
│                       │  ┌──────────┴────────────────────┴─────────────┐  │  │
│                       │  │              Tools                          │  │  │
│                       │  │  analyze_error │ suggest_fix │ run_test     │  │  │
│                       │  └─────────────────────────────────────────────┘  │  │
│                       └──────────────────────────────────────────────────┘  │
│                                          │                                   │
│                                          ▼                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentCore Memory Service                            │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                   Episodic Strategy                              │  │  │
│  │  │                                                                  │  │  │
│  │  │   ┌──────────────┐   ┌───────────────┐   ┌─────────────────┐   │  │  │
│  │  │   │  Extraction  │──▶│ Consolidation │──▶│   Reflection    │   │  │  │
│  │  │   │              │   │               │   │                 │   │  │  │
│  │  │   │ Detect when  │   │ Combine into  │   │ Generate cross- │   │  │  │
│  │  │   │ episode ends │   │ single record │   │ episode insights│   │  │  │
│  │  │   └──────────────┘   └───────────────┘   └─────────────────┘   │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────┐  ┌─────────────────────────────────┐ │  │
│  │  │        Episodes             │  │         Reflections             │ │  │
│  │  │  /debug/actor/{id}/episodes │  │  /debug/actor/{id}/reflections  │ │  │
│  │  │                             │  │                                 │ │  │
│  │  │  • Situation                │  │  • Successful patterns          │ │  │
│  │  │  • Intent                   │  │  • Common failure modes         │ │  │
│  │  │  • Assessment               │  │  • Best practices               │ │  │
│  │  │  • Justification            │  │  • Lessons learned              │ │  │
│  │  └─────────────────────────────┘  └─────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Data Flow:
1. Developer asks debugging question
2. MessageAdded hook retrieves relevant past episodes & reflections
3. Agent processes query with historical context
4. Agent uses tools (analyze_error, suggest_fix, run_test)
5. AfterInvocation hook saves interaction as event
6. AgentCore extracts episodes when conversation completes (~1 min)
7. Reflections generated across multiple episodes (background)
```

## Available Sample Notebooks

| Framework | Use Case | Description | Notebook |
|-----------|----------|-------------|----------|
| Strands Agent | Code Assistant | Debugging assistant that learns from successful resolution patterns | [code-assistant.ipynb](./code-assistant.ipynb) |

## Getting Started

1. Navigate to this folder
2. Install requirements: `pip install -r requirements.txt`
3. Open the Jupyter notebook and follow the step-by-step implementation

## Sample Prompts

Try these debugging queries to test episodic memory learning:

### 1. Similar Error Recall
**Prompt**: "I'm getting KeyError: 'username' when accessing config['username']"

**Expected Behavior**: Agent references past KeyError episode and suggests using `.get()` method for safe dictionary access.

### 2. Pattern Application
**Prompt**: "TypeError when concatenating: result = count + ' items'"

**Expected Behavior**: Agent applies learned type conversion patterns from past episodes.

### 3. Generalization
**Prompt**: "IndexError: list index out of range when accessing items[5] but list has 3 items"

**Expected Behavior**: Agent generalizes from past episodes to suggest bounds checking before list access.

### 4. Complex Workflow
**Prompt**: "My function processes a list of users but crashes with KeyError sometimes"

**Expected Behavior**: Multi-step debugging using tools, demonstrating how the agent chains analyze_error, suggest_fix, and run_test.

### 5. Pattern Recognition
**Prompt**: "Another KeyError! This time accessing data['timestamp'] in my logging code."

**Expected Behavior**: Agent recognizes the KeyError pattern and immediately suggests the defensive .get() approach without needing detailed analysis.

### 6. Unknown Error
**Prompt**: "RecursionError: maximum recursion depth exceeded in my tree traversal function"

**Expected Behavior**: Agent acknowledges this is a new error type with no past episodes, provides general guidance on recursion limits and base cases.

## Key Concepts

### Episodes vs Reflections

**Episodes** capture individual interaction sequences:
- A debugging session where the agent tried multiple approaches
- A customer support conversation that resolved an issue
- A data processing workflow with specific parameters

**Reflections** analyze patterns across episodes:
- Which tool combinations consistently succeed
- Common failure modes and their resolutions
- Best practices extracted from successful episodes

### Retrieval Best Practices

1. **Query by intent**: Episodes are indexed by "intent", reflections by "use case"
2. **Include tool results**: When creating events, include `TOOL` results for optimal extraction
3. **Use reflections proactively**: Query reflections at task start to avoid known pitfalls
4. **Linearize successful episodes**: Feed successful episode turns to focus the agent

## Next Steps

After mastering episodic memory:
- Combine with semantic memory for comprehensive agent experiences
- Implement cross-agent reflection sharing for team learning
- Build feedback loops to improve episode detection

## Troubleshooting

### Episodes Not Appearing
**Issue**: No episodes found after running tests

**Solution**: Episode extraction takes approximately 1 minute after a conversation completes. Wait and retry retrieval. Episodes are extracted asynchronously in the background.

### Permission Errors
**Issue**: `AccessDeniedException` when creating memory or saving events

**Solution**: Ensure your AWS credentials have the necessary permissions:
- Policy: `BedrockAgentCoreFullAccess` (managed policy)
- Or custom policy with `bedrock-agentcore:*` permissions

### Model Access Errors
**Issue**: Cannot access Claude Haiku 4.5 model

**Solution**: Enable model access in the AWS Bedrock console:
1. Navigate to AWS Console → Bedrock → Model access
2. Request access for "Anthropic Claude Haiku 4.5"
3. Wait for approval (usually instant for standard models)

### Empty Reflection Results
**Issue**: Reflections namespace returns no results

**Solution**: Reflections are generated after multiple episodes are collected. Run additional debugging sessions with varied scenarios to accumulate episodes. Reflection generation happens in the background and may take several minutes.

### Memory Creation Fails with "Already Exists"
**Issue**: Memory resource with same name already exists

**Solution**: The code handles this automatically by reusing the existing memory. If you want to start fresh, delete the old memory first using `client.delete_memory_and_wait(memory_id=memory_id)`.

## Clean Up

After completing the tutorial, delete the memory resource to avoid ongoing charges:

```python
try:
    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"✅ Deleted memory resource: {memory_id}")
except Exception as e:
    print(f"❌ Error deleting memory: {e}")
```

**Note**: This permanently deletes all episodes and reflections stored for this memory resource. Make sure to export any data you want to keep before deletion.

**Cost Considerations**: AgentCore Memory pricing is based on storage and retrieval. Regular cleanup of development/test memory resources helps control costs.
