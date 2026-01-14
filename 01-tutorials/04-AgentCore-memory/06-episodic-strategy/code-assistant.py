"""
AgentCore Episodic Memory - Code Debugging Assistant

This tutorial demonstrates how to build a code debugging assistant using
Strands agents integrated with AgentCore Episodic Memory. The agent learns
from past debugging sessions, remembering which approaches worked and which
failed, enabling it to resolve similar issues more efficiently over time.

Tutorial Details:
- Tutorial type: Long term Episodic
- Agent type: Code Debugging Assistant  
- Agentic Framework: Strands Agents
- LLM model: Anthropic Claude Haiku 4.5
- Components: AgentCore Episodic Memory with Reflections

You'll learn to:
- Set up AgentCore Memory with the Episodic strategy
- Create memory hooks for automatic episode capture
- Retrieve past episodes and reflections to improve agent performance
- Build an agent that learns from experience
"""

# %% [markdown]
# ## Step 1: Install Dependencies and Setup

# %%
# !pip install -qr requirements.txt

# %%
import logging
import json
from typing import Dict, List
from datetime import datetime
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("code-assistant")

from strands import Agent, tool
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry, MessageAddedEvent

# %%
# Configuration
REGION = "us-west-2"
DEVELOPER_ID = "developer_001"
SESSION_ID = f"debug_{datetime.now().strftime('%Y%m%d%H%M%S')}"

# %% [markdown]
# ## Step 2: Create Memory Resource with Episodic Strategy
#
# The episodic strategy automatically:
# - Detects when episodes complete within conversations
# - Extracts structured episode records (situation, intent, assessment, justification)
# - Generates reflections that identify patterns across episodes

# %%
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType

client = MemoryClient(region_name=REGION)
memory_name = "CodeAssistantEpisodicMemory"

# Define episodic memory strategy
strategies = [
    {
        StrategyType.EPISODIC.value: {
            "name": "DebuggingEpisodes",
            "description": "Captures debugging sessions and generates reflections on successful patterns",
            "namespaces": ["debug/actor/{actorId}/episodes"],
            "reflectionConfiguration": {
                "namespaces": ["debug/actor/{actorId}"]
            }
        }
    }
]

# Create memory resource
try:
    memory = client.create_memory_and_wait(
        name=memory_name,
        strategies=strategies,
        description="Episodic memory for code debugging assistant",
        event_expiry_days=180,  # Keep episodes for 6 months
    )
    memory_id = memory['id']
    logger.info(f"✅ Created memory: {memory_id}")
except ClientError as e:
    if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
        memories = client.list_memories()
        memory_id = next((m['id'] for m in memories if m['id'].startswith(memory_name)), None)
        logger.info(f"Memory already exists. Using: {memory_id}")
    else:
        raise
except Exception as e:
    logger.error(f"❌ ERROR: {e}")
    raise

# %%
# Verify episodic strategy is configured
strategies = client.get_memory_strategies(memory_id)
print(json.dumps(strategies, indent=2, default=str))

# %% [markdown]
# ## Step 3: Create Debugging Tools

# %%
@tool
def analyze_error(error_message: str, code_snippet: str) -> str:
    """Analyze an error message and code snippet to identify potential causes.
    
    Args:
        error_message: The error message to analyze
        code_snippet: The relevant code snippet
    
    Returns:
        Analysis of potential causes and suggested fixes
    """
    # Simulate error analysis
    analyses = {
        "TypeError": "Type mismatch detected. Check variable types and function signatures.",
        "KeyError": "Dictionary key not found. Verify key exists before access or use .get().",
        "IndexError": "List index out of range. Check list length before accessing indices.",
        "AttributeError": "Object doesn't have this attribute. Verify object type and available methods.",
        "ImportError": "Module import failed. Check module installation and import path.",
    }
    
    for error_type, analysis in analyses.items():
        if error_type in error_message:
            return f"Analysis: {analysis}\n\nCode context:\n{code_snippet[:200]}"
    
    return f"General error analysis needed for: {error_message}"


@tool
def suggest_fix(error_type: str, context: str) -> str:
    """Suggest a fix for a specific error type.
    
    Args:
        error_type: The type of error (e.g., TypeError, KeyError)
        context: Additional context about the error
    
    Returns:
        Suggested fix with code example
    """
    fixes = {
        "TypeError": "Add type checking: `if isinstance(var, expected_type):`",
        "KeyError": "Use safe access: `value = dict.get('key', default_value)`",
        "IndexError": "Add bounds check: `if index < len(list):`",
        "AttributeError": "Add hasattr check: `if hasattr(obj, 'attr'):`",
        "ImportError": "Try: `pip install module_name` or check PYTHONPATH",
    }
    
    fix = fixes.get(error_type, "Review the error context and stack trace for clues.")
    return f"Suggested fix for {error_type}:\n{fix}\n\nContext: {context}"


@tool  
def run_test(test_description: str) -> str:
    """Simulate running a test to verify a fix.
    
    Args:
        test_description: Description of what to test
    
    Returns:
        Test result (pass/fail with details)
    """
    # Simulate test execution
    import random
    passed = random.random() > 0.3  # 70% success rate for demo
    
    if passed:
        return f"✅ TEST PASSED: {test_description}"
    else:
        return f"❌ TEST FAILED: {test_description} - Additional debugging needed"


logger.info("✅ Debugging tools ready")

# %% [markdown]
# ## Step 4: Create Episodic Memory Hook Provider
#
# The hook provider:
# - Retrieves relevant past episodes and reflections before processing queries
# - Saves debugging interactions as events for episode extraction
# - Episodes are automatically detected and extracted by AgentCore

# %%
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Get namespace mapping for memory strategies."""
    strategies = mem_client.get_memory_strategies(memory_id)
    result = {}
    for strategy in strategies:
        reflection_config = strategy.get("reflectionConfiguration", {})
        result[strategy["type"]] = {
            "namespaces": strategy.get("namespaces", []),
            "reflectionNamespaces": reflection_config.get("namespaces", [])
        }
    return result


class EpisodicMemoryHooks(HookProvider):
    """Memory hooks for episodic memory with reflections."""
    
    def __init__(self, memory_id: str, client: MemoryClient):
        self.memory_id = memory_id
        self.client = client
        self.namespaces = get_namespaces(self.client, self.memory_id)
    
    def retrieve_episodes_and_reflections(self, event: MessageAddedEvent):
        """Retrieve relevant episodes and reflections before processing."""
        messages = event.agent.messages
        if messages[-1]["role"] != "user" or "toolResult" in messages[-1]["content"][0]:
            return
            
        user_query = messages[-1]["content"][0]["text"]
        actor_id = event.agent.state.get("actor_id")
        
        if not actor_id:
            logger.warning("Missing actor_id in agent state")
            return
        
        try:
            all_context = []
            episodic_config = self.namespaces.get("EPISODIC", {})
            
            # Retrieve relevant episodes (indexed by "intent")
            for namespace_template in episodic_config.get("namespaces", []):
                namespace = namespace_template.format(actorId=actor_id)
                episodes = self.client.retrieve_memories(
                    memory_id=self.memory_id,
                    namespace=namespace,
                    query=user_query,  # Episodes indexed by intent
                    top_k=3
                )
                
                for episode in episodes:
                    if isinstance(episode, dict):
                        content = episode.get('content', {})
                        if isinstance(content, dict):
                            text = content.get('text', '').strip()
                            if text:
                                all_context.append(f"[PAST EPISODE] {text}")
            
            # Retrieve reflections (indexed by "use case")
            for namespace_template in episodic_config.get("reflectionNamespaces", []):
                namespace = namespace_template.format(actorId=actor_id)
                reflections = self.client.retrieve_memories(
                    memory_id=self.memory_id,
                    namespace=namespace,
                    query=user_query,  # Reflections indexed by use case
                    top_k=2
                )
                
                for reflection in reflections:
                    if isinstance(reflection, dict):
                        content = reflection.get('content', {})
                        if isinstance(content, dict):
                            text = content.get('text', '').strip()
                            if text:
                                all_context.append(f"[REFLECTION] {text}")
            
            # Inject context into query
            if all_context:
                context_text = "\n".join(all_context)
                original_text = messages[-1]["content"][0]["text"]
                messages[-1]["content"][0]["text"] = (
                    f"Past Experience:\n{context_text}\n\nCurrent Query: {original_text}"
                )
                logger.info(f"Retrieved {len(all_context)} episodes/reflections")
                
        except Exception as e:
            logger.error(f"Failed to retrieve episodes: {e}")
    
    def save_debugging_interaction(self, event: AfterInvocationEvent):
        """Save debugging interaction for episode extraction."""
        try:
            messages = event.agent.messages
            if len(messages) < 2 or messages[-1]["role"] != "assistant":
                return
            
            # Collect the full interaction including tool uses
            interaction_messages = []
            for msg in messages:
                role = msg["role"].upper()
                content = msg["content"]
                
                if isinstance(content, list):
                    for item in content:
                        if "text" in item:
                            interaction_messages.append((item["text"], role))
                        elif "toolUse" in item:
                            # Include tool usage for better episode extraction
                            tool_info = item["toolUse"]
                            tool_text = f"[TOOL: {tool_info.get('name', 'unknown')}]"
                            interaction_messages.append((tool_text, "TOOL"))
                        elif "toolResult" in item:
                            result = item["toolResult"].get("content", [{}])[0].get("text", "")
                            interaction_messages.append((f"[RESULT: {result[:200]}]", "TOOL"))
            
            if interaction_messages:
                actor_id = event.agent.state.get("actor_id")
                session_id = event.agent.state.get("session_id")
                
                if not actor_id or not session_id:
                    logger.warning("Missing actor_id or session_id")
                    return
                
                # Save event - AgentCore will automatically detect episode completion
                self.client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=interaction_messages
                )
                logger.info("Saved debugging interaction for episode extraction")
                
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
    
    def register_hooks(self, registry: HookRegistry) -> None:
        """Register episodic memory hooks."""
        registry.add_callback(MessageAddedEvent, self.retrieve_episodes_and_reflections)
        registry.add_callback(AfterInvocationEvent, self.save_debugging_interaction)
        logger.info("Episodic memory hooks registered")

# %% [markdown]
# ## Step 5: Create Code Debugging Agent

# %%
episodic_hooks = EpisodicMemoryHooks(memory_id, client)

debug_agent = Agent(
    hooks=[episodic_hooks],
    model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
    tools=[analyze_error, suggest_fix, run_test],
    state={"actor_id": DEVELOPER_ID, "session_id": SESSION_ID},
    system_prompt="""You are an expert code debugging assistant with memory of past debugging sessions.

Your role:
- Help developers identify and fix code errors
- Use past episodes to recognize similar issues you've solved before
- Apply reflections to avoid approaches that previously failed
- Document your debugging process for future learning

When you see [PAST EPISODE] context, use it to inform your approach.
When you see [REFLECTION] context, apply those learned patterns.

Always:
1. Analyze the error systematically
2. Reference relevant past experience if available
3. Suggest specific fixes with code examples
4. Verify fixes work when possible"""
)

print("✅ Code debugging agent created with episodic memory")

# %% [markdown]
# ## Step 6: Seed Past Debugging Episodes
#
# Let's add some previous debugging sessions to demonstrate episodic memory.

# %%
# Seed with previous debugging sessions
past_sessions = [
    # Session 1: KeyError debugging
    ("I'm getting a KeyError when accessing user['email'] in my Flask app.", "USER"),
    ("Let me analyze this KeyError issue.", "ASSISTANT"),
    ("[TOOL: analyze_error]", "TOOL"),
    ("[RESULT: Dictionary key not found. Verify key exists before access.]", "TOOL"),
    ("The issue is that 'email' key doesn't exist. Use user.get('email', '') for safe access.", "ASSISTANT"),
    ("[TOOL: suggest_fix]", "TOOL"),
    ("[RESULT: Use safe access: value = dict.get('key', default_value)]", "TOOL"),
    ("Fixed! I changed to user.get('email', 'no-email@example.com') and it works.", "USER"),
    ("[TOOL: run_test]", "TOOL"),
    ("[RESULT: ✅ TEST PASSED: KeyError fix verification]", "TOOL"),
    ("Great! The fix is verified. Remember to always use .get() for optional dictionary keys.", "ASSISTANT"),
    
    # Session 2: TypeError debugging
    ("TypeError: can't multiply sequence by non-int of type 'str' in my calculation.", "USER"),
    ("This is a type coercion issue. Let me analyze.", "ASSISTANT"),
    ("[TOOL: analyze_error]", "TOOL"),
    ("[RESULT: Type mismatch detected. Check variable types.]", "TOOL"),
    ("You're trying to multiply a string by another string. Convert to int first: int(value) * multiplier", "ASSISTANT"),
    ("[TOOL: run_test]", "TOOL"),
    ("[RESULT: ✅ TEST PASSED: Type conversion fix]", "TOOL"),
    ("That fixed it! I added int() conversion before the multiplication.", "USER"),
]

try:
    client.create_event(
        memory_id=memory_id,
        actor_id=DEVELOPER_ID,
        session_id="seed_session_001",
        messages=past_sessions
    )
    print("✅ Seeded past debugging episodes")
    print("⏳ Note: Episode extraction happens in background (~1 minute)")
except Exception as e:
    print(f"⚠️ Error seeding history: {e}")

# %% [markdown]
# ## Step 7: Test Debugging Scenarios
#
# The agent should now leverage past episodes and reflections.

# %%
# Test 1: Similar KeyError issue - should reference past episode
response1 = debug_agent("I'm getting KeyError: 'username' when I try to access config['username']")
print(f"Agent: {response1}")

# %%
# Test 2: New TypeError - should apply learned patterns
response2 = debug_agent("Getting TypeError when concatenating: result = count + ' items'")
print(f"Agent: {response2}")

# %%
# Test 3: IndexError - new error type
response3 = debug_agent("IndexError: list index out of range when accessing items[5] but list has 3 items")
print(f"Agent: {response3}")

# %%
# Test 4: Multi-step debugging workflow
response4 = debug_agent("""
I have a complex issue. My function processes a list of users:

def process_users(users):
    for user in users:
        email = user['email']
        send_notification(email)

It crashes with KeyError sometimes. How do I make it robust?
""")
print(f"Agent: {response4}")

# %%
# Test 5: Learning from reflection - agent should recognize pattern
response5 = debug_agent("Another KeyError! This time accessing data['timestamp'] in my logging code.")
print(f"Agent: {response5}")

# %%
# Test 6: Completely new error type to see how agent handles unknowns
response6 = debug_agent("RecursionError: maximum recursion depth exceeded in my tree traversal function")
print(f"Agent: {response6}")

# %% [markdown]
# ## Step 8: Verify Episode Storage

# %%
print("\n📚 Episodic Memory Summary:")
print("=" * 50)

episodic_config = get_namespaces(client, memory_id).get("EPISODIC", {})

# Check episodes
for namespace_template in episodic_config.get("namespaces", []):
    namespace = namespace_template.format(actorId=DEVELOPER_ID)
    
    try:
        episodes = client.retrieve_memories(
            memory_id=memory_id,
            namespace=namespace,
            query="debugging error fix",
            top_k=5
        )
        
        print(f"\nEPISODES ({len(episodes)} found):")
        for i, episode in enumerate(episodes, 1):
            if isinstance(episode, dict):
                content = episode.get('content', {})
                if isinstance(content, dict):
                    text = content.get('text', '')[:200] + "..."
                    print(f"  {i}. {text}")
                    
    except Exception as e:
        print(f"Error retrieving episodes: {e}")

# Check reflections
for namespace_template in episodic_config.get("reflectionNamespaces", []):
    namespace = namespace_template.format(actorId=DEVELOPER_ID)
    
    try:
        reflections = client.retrieve_memories(
            memory_id=memory_id,
            namespace=namespace,
            query="debugging patterns",
            top_k=3
        )
        
        print(f"\nREFLECTIONS ({len(reflections)} found):")
        for i, reflection in enumerate(reflections, 1):
            if isinstance(reflection, dict):
                content = reflection.get('content', {})
                if isinstance(content, dict):
                    text = content.get('text', '')[:200] + "..."
                    print(f"  {i}. {text}")
                    
    except Exception as e:
        print(f"Error retrieving reflections: {e}")

print("\n" + "=" * 50)

# %% [markdown]
# ## Key Takeaways
#
# 1. **Episodic memory captures interaction sequences**, not just facts
# 2. **Reflections emerge automatically** from analyzing multiple episodes
# 3. **Include tool results** in events for richer episode extraction
# 4. **Query by intent** for episodes, **by use case** for reflections
# 5. **Episode extraction is asynchronous** (~1 minute after conversation ends)
#
# ## Clean Up

# %%
# Uncomment to delete the memory resource
# try:
#     client.delete_memory_and_wait(memory_id=memory_id)
#     print(f"✅ Deleted memory resource: {memory_id}")
# except Exception as e:
#     print(f"Error deleting memory: {e}")
