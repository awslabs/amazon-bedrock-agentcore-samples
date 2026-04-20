"""
Memory hooks for slide deck agent - integrates user preferences with Strands agents
"""

import logging
import json
from typing import List, Dict, Any, Optional
from strands.hooks import (
    AfterInvocationEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)
from bedrock_agentcore.memory.constants import (
    ConversationalMessage,
    MessageRole,
    RetrievalConfig,
)
from bedrock_agentcore.memory.session import MemorySession
from bedrock_agentcore.memory.models import MemoryRecord

# Define message role constants
USER = MessageRole.USER
ASSISTANT = MessageRole.ASSISTANT

logger = logging.getLogger(__name__)


class SlideMemoryHooks(HookProvider):
    """Memory hooks for slide deck agent with user preference integration"""

    def __init__(self, memory_session: MemorySession):
        """Initialize with a MemorySession for user preferences"""
        self.memory_session = memory_session

        # Configure retrieval for user preferences
        self.preference_retrieval_config = RetrievalConfig(
            top_k=5,  # Get top 5 relevant preference memories
            relevance_score=0.2,  # Lower threshold to capture more preferences
        )

    def _extract_message_text(self, message: Dict[str, Any]) -> Optional[str]:
        """Safely extract text content from a Strands message"""
        try:
            # Handle different possible message structures
            content = message.get("content", [])

            # Handle case where content is a list
            if isinstance(content, list) and len(content) > 0:
                first_content = content[0]

                # Check for text field
                if isinstance(first_content, dict) and "text" in first_content:
                    return first_content["text"]

                # Check for toolResult (skip these)
                if isinstance(first_content, dict) and "toolResult" in first_content:
                    return None

                # Handle case where content item is just a string
                if isinstance(first_content, str):
                    return first_content

            # Handle case where content is directly a string
            if isinstance(content, str):
                return content

            # Handle case where message has direct text field
            if "text" in message:
                return message["text"]

            return None
        except Exception as e:
            logger.debug(f"Error extracting text from message: {e}")
            return None

    def _is_tool_result_message(self, message: Dict[str, Any]) -> bool:
        """Check if message contains tool results (should be skipped for user preferences)"""
        try:
            content = message.get("content", [])
            if isinstance(content, list) and len(content) > 0:
                first_content = content[0]
                if isinstance(first_content, dict) and "toolResult" in first_content:
                    return True
            return False
        except Exception:
            return False

    def _parse_structured_preference(
        self, memory_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse structured preference from memory content"""
        try:
            # The content might be JSON string or already parsed
            if isinstance(memory_content, str):
                parsed = json.loads(memory_content)
            else:
                parsed = memory_content

            # Handle case where it's a list of preferences
            if isinstance(parsed, list) and len(parsed) > 0:
                parsed = parsed[0]  # Take first preference

            # Ensure we have the expected structure
            if isinstance(parsed, dict):
                return {
                    "context": parsed.get("context", ""),
                    "preference": parsed.get("preference", ""),
                    "categories": parsed.get("categories", []),
                }

            # Fallback to treating as simple text
            return {
                "context": "Legacy format",
                "preference": str(parsed),
                "categories": ["general"],
            }
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.debug(f"Error parsing structured preference: {e}")
            # Fallback to simple text
            return {
                "context": "Parsing error",
                "preference": str(memory_content),
                "categories": ["general"],
            }

    def retrieve_user_preferences(self, event: MessageAddedEvent):
        """Retrieve user style preferences before processing slide requests"""
        messages = event.agent.messages
        if not messages or messages[-1]["role"] != "user":
            return

        # Check if this is a slide-related request
        user_query = self._extract_message_text(messages[-1])
        if not user_query or not self._is_slide_request(user_query):
            logger.debug("🔍 Not a slide request, skipping preference injection")
            return

        logger.info("🎯 MEMORY HOOK: Retrieving user preferences for slide request")
        logger.info(f"📝 Query: {user_query[:100]}...")

        try:
            # Search for user preferences in memory
            preference_namespace = (
                f"slidedecks/user/{self.memory_session._actor_id}/style_preferences"
            )
            logger.info(f"🔎 Searching namespace: {preference_namespace}")

            # Search for relevant preferences based on the query
            preference_memories = self.memory_session.search_long_term_memories(
                query=user_query,
                namespace_prefix=preference_namespace,
                top_k=self.preference_retrieval_config.top_k,
            )

            logger.info(
                f"🔎 Found {len(preference_memories)} preference memories in search"
            )

            # Filter by relevance score
            min_score = self.preference_retrieval_config.relevance_score
            relevant_preferences = [
                memory
                for memory in preference_memories
                if memory.get("score", 0) >= min_score
            ]

            logger.info(
                f"📊 Filtered to {len(relevant_preferences)} relevant preferences (min_score: {min_score})"
            )

            if relevant_preferences:
                # Log what preferences are being used
                for i, pref in enumerate(relevant_preferences[:3], 1):
                    score = pref.get("score", 0)
                    content = pref.get("content", {})
                    pref_text = content.get("text", "Unknown preference")[:50]
                    logger.info(f"   {i}. [Score: {score:.2f}] {pref_text}...")

                # Format and inject preferences into agent context
                preference_context = self._format_preferences(relevant_preferences)
                self._inject_preference_context(event.agent, preference_context)
                logger.info(
                    f"✅ INJECTED {len(relevant_preferences)} user preferences into slide generation context"
                )
                logger.debug(
                    f"📋 Injected context preview: {preference_context[:200]}..."
                )
            else:
                # No preferences found - this might be a new user
                logger.info(
                    "📝 No existing user preferences found - will learn from this interaction"
                )

        except Exception as e:
            logger.error(f"Failed to retrieve user preferences: {e}")

    def _is_slide_request(self, query: str) -> bool:
        """Check if the user query is related to slide deck creation"""
        slide_keywords = [
            "slide",
            "presentation",
            "deck",
            "powerpoint",
            "ppt",
            "create",
            "generate",
            "make",
            "build",
            "theme",
            "color",
            "style",
            "design",
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in slide_keywords)

    def _format_preferences(self, preference_memories: List[MemoryRecord]) -> str:
        """Format user preferences for structured injection into agent context"""
        if not preference_memories:
            return ""

        # Start with structured preference summary
        preference_lines = [
            "🎨 USER STYLE PREFERENCES DETECTED:",
            "The following learned preferences should influence your tool parameter choices:",
            "",
        ]

        # Track extracted parameters for summary
        extracted_params = {
            "color_scheme": None,
            "use_gradients": None,
            "use_shadows": None,
            "font_family": None,
            "presentation_type": None,
            "header_style": None,
        }

        # Process each preference and extract actionable parameters
        for i, memory in enumerate(
            preference_memories[:5], 1
        ):  # Increased to 5 for more context
            memory_content = memory.get("content", {})
            structured_pref = self._parse_structured_preference(memory_content)

            preference = structured_pref.get("preference", "No preference available")
            context = structured_pref.get("context", "")
            score = memory.get("score", 0)

            # Analyze preference text for parameters
            pref_lower = preference.lower()

            # Extract color preferences
            for color in ["blue", "purple", "green", "red"]:
                if color in pref_lower and not extracted_params["color_scheme"]:
                    extracted_params["color_scheme"] = color

            # Extract gradient preferences
            if any(
                term in pref_lower
                for term in ["solid color", "no gradient", "solid background"]
            ):
                extracted_params["use_gradients"] = False
            elif "gradient" in pref_lower and "prefer" in pref_lower:
                extracted_params["use_gradients"] = True

            # Extract shadow preferences
            if any(term in pref_lower for term in ["no shadow", "clean", "minimal"]):
                extracted_params["use_shadows"] = False
            elif "shadow" in pref_lower and "prefer" in pref_lower:
                extracted_params["use_shadows"] = True

            # Extract font preferences
            for font in ["modern", "classic", "technical", "creative"]:
                if font in pref_lower and not extracted_params["font_family"]:
                    extracted_params["font_family"] = font

            # Extract presentation type preferences
            for ptype in ["tech", "business", "academic", "creative"]:
                if ptype in pref_lower and not extracted_params["presentation_type"]:
                    extracted_params["presentation_type"] = ptype

            # Format individual preference
            pref_line = f"{i}. [{score:.1f}] {preference}"
            if context:
                pref_line += f" (Context: {context})"
            preference_lines.append(pref_line)

        # Add structured parameter recommendations
        preference_lines.extend(
            ["", "📋 RECOMMENDED TOOL PARAMETERS (based on above preferences):"]
        )

        param_recommendations = []
        if extracted_params["color_scheme"]:
            param_recommendations.append(
                f"- color_scheme: '{extracted_params['color_scheme']}'"
            )
        if extracted_params["use_gradients"] is not None:
            param_recommendations.append(
                f"- use_gradients: {extracted_params['use_gradients']}"
            )
        if extracted_params["use_shadows"] is not None:
            param_recommendations.append(
                f"- use_shadows: {extracted_params['use_shadows']}"
            )
        if extracted_params["font_family"]:
            param_recommendations.append(
                f"- font_family: '{extracted_params['font_family']}'"
            )
        if extracted_params["presentation_type"]:
            param_recommendations.append(
                f"- presentation_type: '{extracted_params['presentation_type']}'"
            )
        if extracted_params["header_style"]:
            param_recommendations.append(
                f"- header_style: '{extracted_params['header_style']}'"
            )

        if param_recommendations:
            preference_lines.extend(param_recommendations)
        else:
            preference_lines.append("- No specific parameter overrides detected")

        preference_lines.extend(
            [
                "",
                "💡 INSTRUCTIONS:",
                "- Apply these parameters when calling create_advanced_slides_tool()",
                "- These represent learned user preferences from past interactions",
                "- Only override if user explicitly requests different styling in current request",
                "",
            ]
        )

        return "\\n".join(preference_lines)

    def _inject_preference_context(self, agent, preference_context: str):
        """Inject user preferences into the agent's system prompt"""
        original_prompt = agent.system_prompt
        enhanced_prompt = f"{original_prompt}\\n\\n{preference_context}"
        agent.system_prompt = enhanced_prompt

    def save_slide_interaction(self, event: AfterInvocationEvent):
        """Save slide-related interactions to build user preference history"""
        try:
            messages = event.agent.messages
            if len(messages) < 2 or messages[-1]["role"] != "assistant":
                return

            # Get the last user query and agent response
            user_query = None
            agent_response = None

            for msg in reversed(messages):
                if msg["role"] == "assistant" and not agent_response:
                    agent_response = self._extract_message_text(msg)
                elif msg["role"] == "user" and not user_query:
                    extracted_text = self._extract_message_text(msg)
                    # Skip tool results, only capture user text input
                    if extracted_text and not self._is_tool_result_message(msg):
                        user_query = extracted_text
                        break

            if not user_query or not agent_response:
                return

            # Only save slide-related interactions
            if not self._is_slide_request(user_query):
                return

            # Check if this interaction contains preference information
            if self._contains_preference_info(user_query, agent_response):
                # Save the interaction to memory
                interaction_messages = [
                    ConversationalMessage(user_query, USER),
                    ConversationalMessage(agent_response, ASSISTANT),
                ]

                result = self.memory_session.add_turns(interaction_messages)
                logger.info(
                    f"✅ Saved slide interaction with preferences - Event ID: {result['eventId']}"
                )

        except Exception as e:
            logger.error(f"Failed to save slide interaction: {e}")

    def _contains_preference_info(self, user_query: str, agent_response: str) -> bool:
        """Check if the interaction contains user preference information worth storing"""

        # Look for preference indicators in user query
        preference_indicators = [
            "prefer",
            "like",
            "want",
            "choose",
            "use",
            "color",
            "theme",
            "style",
            "font",
            "design",
            "blue",
            "green",
            "purple",
            "red",
            "professional",
            "modern",
            "classic",
            "creative",
            "tech",
            "business",
            "academic",
        ]

        combined_text = f"{user_query} {agent_response}".lower()
        return any(indicator in combined_text for indicator in preference_indicators)

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register slide deck memory hooks with the agent"""
        registry.add_callback(MessageAddedEvent, self.retrieve_user_preferences)
        registry.add_callback(AfterInvocationEvent, self.save_slide_interaction)
        logger.info("✅ Slide deck memory hooks registered")


class SlideMemoryHookManager:
    """Manager for creating and configuring slide memory hooks"""

    def __init__(self, memory_session: MemorySession):
        self.memory_session = memory_session
        self.hooks = SlideMemoryHooks(memory_session)

    def get_hooks(self) -> SlideMemoryHooks:
        """Get the configured memory hooks for use with Strands agents"""
        return self.hooks

    def create_hooks_for_user(self, actor_id: str, session_id: str) -> SlideMemoryHooks:
        """Create memory hooks for a specific user session"""
        # Note: In a production system, you'd create a new MemorySession here
        # For this demo, we'll use the existing session but could extend this
        return self.hooks


# Example usage for testing
def create_slide_memory_hooks(memory_session: MemorySession) -> SlideMemoryHooks:
    """Create slide memory hooks for integration with Strands agents"""

    logger.info("Creating slide memory hooks...")
    hooks = SlideMemoryHooks(memory_session)
    logger.info("✅ Slide memory hooks created successfully")

    return hooks


if __name__ == "__main__":
    # This would be used in conjunction with memory_setup.py
    print(
        "Slide memory hooks module - use with memory_setup.py to create full integration"
    )
    print("Example usage:")
    print("  from memory_setup import setup_slide_deck_memory")
    print("  from memory_hooks.slide_hooks import create_slide_memory_hooks")
    print("  memory, session_mgr, mgr = setup_slide_deck_memory()")
    print("  session = session_mgr.create_memory_session('user123', 'session456')")
    print("  hooks = create_slide_memory_hooks(session)")
