"""
Enhanced slide deck agent with memory capabilities for user preference learning
"""

import json
import logging
import os
import sys
from typing import Any, Dict, List

from bedrock_agentcore.memory.session import MemorySession
from config import BEDROCK_MODEL_ID, OUTPUT_DIR
from generators.html_generator import HTMLSlideGenerator
from memory_hooks.slide_hooks import SlideMemoryHooks
from strands import Agent, tool

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# PowerPoint conversion removed - HTML only

logger = logging.getLogger(__name__)


class MemoryEnabledSlideDeckAgent:
    """Enhanced slide deck agent with memory capabilities for learning user preferences"""

    def __init__(self, memory_session: MemorySession, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        self.memory_session = memory_session
        self.html_generator = HTMLSlideGenerator(output_dir)

        # Create memory hooks
        self.memory_hooks = SlideMemoryHooks(memory_session)

        # Create the enhanced Strands agent with memory integration
        self.agent = Agent(
            model=BEDROCK_MODEL_ID,
            hooks=[self.memory_hooks],  # Memory hooks for automatic preference learning
            tools=[
                self.create_advanced_slides_tool,
                self.get_user_preferences_tool,
                self.recommend_style_tool,
            ],
            system_prompt=self._get_enhanced_system_prompt(),
        )

    def _get_enhanced_system_prompt(self) -> str:
        """Get the enhanced system prompt for the memory-enabled agent"""
        return """You are an intelligent slide deck creation assistant with memory capabilities.
You learn and remember user preferences to create increasingly personalized presentations.

Your enhanced capabilities:
1. **Memory-Driven Personalization**: Learn user preferences for colors, themes, fonts, and presentation styles
2. **Context-Aware Recommendations**: Suggest styles based on presentation type and past preferences
3. **Advanced Styling**: Generate presentations with sophisticated CSS and user-preferred aesthetics
4. **Interactive HTML Output**: Create responsive HTML presentations with navigation and keyboard support
5. **Preference Evolution**: Adapt recommendations as you learn more about user preferences

**CRITICAL: Content Format for create_advanced_slides_tool**:
When calling create_advanced_slides_tool, you MUST format the content parameter using markdown:
- Use # for each new slide title: `# Introduction`
- Use - or * for bullet points: `- Key point 1`
- Use ## for section dividers: `## Section Break`

Example content format:
```
# Introduction
- Welcome to the presentation
- Overview of topics

# Main Topic
- First key point
- Second key point
- Third key point

# Conclusion
- Summary
- Thank you
```

**Your Memory System**:
- Automatically remembers user style choices and feedback
- Learns patterns: "blue themes for tech presentations, elegant fonts for business"
- Suggests improvements based on previous successful combinations
- Adapts to user's evolving preferences over time

**Available Presentation Types**:
- **Tech**: Technical presentations with modern, clean styling
- **Business**: Professional presentations with corporate aesthetics
- **Academic**: Scholarly presentations with traditional, readable styling
- **Creative**: Artistic presentations with bold, expressive design

**Available Styling Controls**:
- Colors: blue, green, purple, red (with smart auto-combinations)
- Fonts: modern (Inter), classic (Georgia), technical (JetBrains Mono), creative (Poppins)
- Gradients: Set use_gradients=False for solid colors, use_gradients=True for gradients
- Shadows: Set use_shadows=False to disable shadows, use_shadows=True to enable
- Spacing: compact, comfortable, spacious (controls overall layout density)
- Borders: 0-20 pixel border radius for rounded corners
- Font Size: 12-24 pixel base font size
- Header Style: bold, elegant, minimal

**Intelligent Recommendations**:
When users don't specify preferences, use memory to suggest appropriate styles:
- Consider presentation topic and audience
- Reference their past successful combinations
- Suggest new variations that align with their established preferences
- Explain why you're recommending specific choices

**MANDATORY WORKFLOW - ALWAYS FOLLOW THIS ORDER**:
1. **FIRST**: Always call get_user_preferences_tool() to retrieve stored preferences before creating any presentation
2. **SECOND**: Extract learned preferences and use them as your default styling parameters
3. **THIRD**: Override with any explicit user instructions (user instructions always win)
4. **FOURTH**: Create presentation using personalized defaults + user overrides
5. **FIFTH**: Explain your styling choices and ask for feedback to improve future suggestions

**Response Strategy**:
- ALWAYS prioritize explicit user instructions over learned preferences
- When user says "solid colors" or "no gradients", set use_gradients=False
- When user says "no shadows", set use_shadows=False
- Use stored preferences for ALL unspecified styling choices
- Never create presentations without first checking memory for user preferences

**HOW TO APPLY STORED PREFERENCES**:
When you get preferences from get_user_preferences_tool(), parse the JSON and PASS styling parameters to the tool:

Example preference parsing:
- If preference mentions "blue colors" → PASS color_scheme="blue" to create_advanced_slides_tool
- If preference mentions "solid colors" or "no gradients" → PASS use_gradients=False to the tool
- If preference mentions "no shadows" → PASS use_shadows=False to the tool
- If preference mentions "modern fonts" → PASS font_family="modern" to the tool
- If preference mentions "business style" → PASS presentation_type="business" to the tool
- If preference mentions "minimal" → PASS header_style="minimal" to the tool

**CRITICAL: User Instructions Override Memory**:
- If user requests "solid blue background", PASS color_scheme="blue" AND use_gradients=False
- If user wants "minimal style with no shadows", PASS use_shadows=False
- Never let learned preferences contradict explicit current instructions

**HOW TO OVERRIDE - TOOL CALL EXAMPLES**:

Example 1 - User wants gradients:
User: "use gradient colors with blue and purple"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=True,
    color_scheme="blue"
)

Example 2 - User wants solid colors:
User: "use solid dark blue background with no shadows"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=False,
    color_scheme="dark-blue",
    use_shadows=False
)

Example 3 - User wants specific font:
User: "use modern professional fonts"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    font_family="modern"
)

Example 4 - User wants dark gradient background (like compliance presentations):
User: "use gradient with dark pink, purple, and dark blue background"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=True,
    color_scheme="dark-blue"
)

Example 5 - User wants light background with specific color:
User: "Use light background with dark green colour theme"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    color_scheme="green"  # green has light background with green accents
)

Example 6 - User wants light background (no specific color):
User: "use light background for this presentation"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    color_scheme="blue"  # default light background
)

Example 7 - User wants multi-color gradient:
User: "dark background with gradient colours such as dark pink, purple and bright blue"
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=True,
    color_scheme="dark-purple"  # Pick most prominent/central color
)

**Note on multiple colors**: When user mentions multiple colors with gradients:
- Identify the MAIN/PRIMARY color (usually middle or most emphasized)
- "dark pink, purple, bright blue" → purple is central → use "dark-purple"
- "blue and green gradient" → use first color mentioned → "blue"
- Set use_gradients=True
- The CSS generator automatically blends into gradient

**CRITICAL - DO NOT IGNORE THIS**:
When user provides explicit styling instructions, you MUST:

1. READ the user's request word-by-word
2. EXTRACT every styling instruction:
   - "light background" → color_scheme="blue" (or green/purple/red if color specified)
   - "dark green" + "light background" → color_scheme="green"
   - "gradient colours" → use_gradients=True
   - "solid colors" or "no gradients" → use_gradients=False
   - "no shadows" → use_shadows=False
   - Multiple colors → pick primary color
3. PASS these parameters in create_advanced_slides_tool() call
4. If you DON'T pass parameters, memory preferences will be used instead

FAILURE MODE TO AVOID:
❌ Agent says: "I'll use light background and green"
❌ Agent calls: create_advanced_slides_tool(content="...", title="...")  ← NO PARAMS
❌ Result: OLD memory preferences (dark-blue) applied, user request IGNORED

✅ CORRECT APPROACH:
✅ Agent says: "I'll use light background and green"
✅ Agent calls: create_advanced_slides_tool(content="...", title="...", color_scheme="green")  ← PARAMS PASSED
✅ Result: User's explicit request applied correctly

Remember: Saying you'll do something ≠ Actually doing it. PASS THE PARAMETERS.

**SIMPLIFIED APPROACH - PASS USER REQUEST**:
To ensure explicit styling is always applied correctly, pass the original user request text:

Example: User wants gradient with dark blue
Tool call: create_advanced_slides_tool(
    content="...",
    title="...",
    user_request="Create a presentation with gradient colors using dark blue background"
)
# The tool will automatically extract: use_gradients=True, color_scheme="dark-blue"

This approach is more reliable because Python code extracts the styling keywords programmatically,
rather than relying on LLM interpretation. Just pass the original request text and the tool handles the rest!

**EXAMPLE WORKFLOW**:
User: "Create a presentation about marketing"
1. Call get_user_preferences_tool() → Returns preferences for "purple colors" and "creative fonts"
2. Set defaults: color_scheme="purple", font_family="creative"
3. Check user request for overrides → None specified
4. Create presentation with: color_scheme="purple", font_family="creative"
5. Explain: "Using your preferred purple color scheme and creative fonts based on past preferences"

Always use the available tools to create presentations and remember to save user feedback for continuous improvement."""

    @tool
    def create_advanced_slides_tool(
        self, content: str, title: str, user_request: str = "", **style_prefs
    ) -> str:
        """Create advanced HTML slides with user preferences learned from memory

        Args:
            content: Slide content in markdown format:
                    # Slide Title
                    - Bullet point 1
                    - Bullet point 2
                    * Alternative bullet syntax
            user_request: Optional original user request text for automatic style extraction

                    ## Section Title (for section dividers)

                    Use # for each new slide title, then add bullet points with - or *
            title: Presentation title
            **style_prefs: Optional style overrides (color_scheme, use_gradients, use_shadows, etc.)
                          If not provided, uses preferences learned from memory

        Returns:
            File path to generated HTML presentation with personalized styling
        """
        try:
            # Valid parameters for generate_presentation
            valid_params = {
                "theme",
                "color_scheme",
                "font_family",
                "use_gradients",
                "use_shadows",
                "border_radius",
                "spacing_style",
                "font_size_base",
                "header_style",
                "preferences",
            }

            # Three-tier merge: saved (memory) → style_prefs (LLM) → explicit (extracted from user_request)
            saved_prefs = self._get_saved_preferences()
            explicit_prefs = self._extract_style_from_request(user_request)
            final_prefs = {
                k: v
                for k, v in {**saved_prefs, **style_prefs, **explicit_prefs}.items()
                if k in valid_params
            }

            logger.info(
                f"🎨 Preference merge - Saved: {saved_prefs}, Explicit: {explicit_prefs}, Final: {final_prefs}"
            )

            # Generate presentation with preferences
            filepath = self.html_generator.generate_presentation(
                content=content, title=title, **final_prefs
            )

            # Add "Memory" suffix to distinguish from basic agent
            dir_name = os.path.dirname(filepath)
            base_name = os.path.basename(filepath)
            name_parts = base_name.rsplit(".", 1)
            new_filepath = os.path.join(
                dir_name, f"{name_parts[0]}_Memory.{name_parts[1]}"
            )
            os.rename(filepath, new_filepath)
            filepath = new_filepath

            logger.info(f"Generated personalized presentation: {filepath}")
            logger.info(f"Applied preferences: {final_prefs}")

            # Create user-friendly response
            color_scheme = final_prefs.get("color_scheme", "default")
            use_gradients = final_prefs.get("use_gradients", True)
            use_shadows = final_prefs.get("use_shadows", True)

            return f"""✅ Personalized presentation created successfully!

📁 File: {os.path.basename(filepath)}
🎨 Style: {color_scheme} color scheme with personalized styling
🖼️  Effects: {"gradients" if use_gradients else "solid colors"}, {"shadows" if use_shadows else "no shadows"}
📍 Full path: {filepath}

The presentation includes:
- Styling based on your learned preferences
- Interactive navigation with keyboard support
- Responsive design for different screen sizes
- Ready to view in any web browser"""

        except Exception as e:
            logger.error(f"Error creating personalized slides: {e}")
            return f"❌ Error creating presentation: {str(e)}"

    # PowerPoint conversion functionality removed - HTML presentations only

    @tool
    def get_user_preferences_tool(self, query: str = "style preferences") -> str:
        """Retrieve current user style preferences from memory

        Args:
            query: Query to search preferences (optional)

        Returns:
            JSON string with structured preferences data for UI rendering
        """
        try:
            # Search for user preferences in memory
            preference_namespace = (
                f"slidedecks/user/{self.memory_session._actor_id}/style_preferences"
            )

            preference_memories = self.memory_session.search_long_term_memories(
                query=query, namespace_prefix=preference_namespace, top_k=5
            )

            if not preference_memories:
                return json.dumps(
                    {
                        "status": "learning",
                        "message": "No established preferences found yet. I'm ready to learn your style preferences!",
                        "preferences": [],
                        "suggestions": [
                            "Try creating presentations with different color schemes",
                            "Experiment with various font styles and themes",
                            "Provide feedback on what works well for your audience",
                            "The agent will automatically learn your preferences",
                        ],
                    }
                )

            # Parse and structure the preferences
            structured_preferences = []
            total_found = len(preference_memories)
            max_display = 5  # Show up to 5 preferences instead of just 3

            logger.info(
                f"Processing {min(max_display, total_found)} of {total_found} preference memories"
            )

            for memory in preference_memories[:max_display]:  # Show top 5 preferences
                try:
                    content_text = memory.get("content", {}).get("text", "")
                    score = memory.get("score", 0)

                    logger.debug(
                        f"Processing memory with score {score}: {content_text[:100]}..."
                    )

                    # Parse the JSON content from memory
                    if content_text.startswith("{") and content_text.endswith("}"):
                        parsed_content = json.loads(content_text)

                        # Extract structured fields
                        preference_item = {
                            "type": self._categorize_preference(
                                parsed_content.get("categories", [])
                            ),
                            "preference": parsed_content.get(
                                "preference", "Unknown preference"
                            ),
                            "context": parsed_content.get("context", ""),
                            "confidence": round(score * 100),  # Convert to percentage
                            "categories": parsed_content.get("categories", []),
                        }
                        structured_preferences.append(preference_item)
                        logger.debug(
                            f"✅ Parsed JSON preference: {preference_item['type']}"
                        )
                    else:
                        # Fallback for non-JSON content
                        preference_item = {
                            "type": "General",
                            "preference": (
                                content_text[:100] + "..."
                                if len(content_text) > 100
                                else content_text
                            ),
                            "context": "Legacy format",
                            "confidence": round(score * 100),
                            "categories": ["general"],
                        }
                        structured_preferences.append(preference_item)
                        logger.debug(
                            f"✅ Parsed legacy preference: {preference_item['preference'][:50]}..."
                        )

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"❌ Error parsing preference memory: {e}")
                    logger.warning(f"   Content: {content_text[:200]}...")
                    continue

            # Create more informative message
            if total_found > len(structured_preferences):
                message = f"Showing {len(structured_preferences)} of {total_found} learned preferences"
            else:
                message = f"Found {len(structured_preferences)} learned preferences"

            return json.dumps(
                {
                    "status": "established" if structured_preferences else "learning",
                    "message": message,
                    "preferences": structured_preferences,
                }
            )

        except Exception as e:
            logger.error(f"Error retrieving preferences: {e}")
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Error retrieving preferences: {str(e)}",
                    "preferences": [],
                }
            )

    def _categorize_preference(self, categories: List[str]) -> str:
        """Categorize preference based on categories list"""
        if not categories:
            return "General"

        # Prioritize certain categories for display
        if any(cat in ["color", "colors", "theme"] for cat in categories):
            return "Color & Theme"
        elif any(cat in ["font", "fonts", "typography"] for cat in categories):
            return "Typography"
        elif any(cat in ["layout", "design", "style"] for cat in categories):
            return "Design Style"
        elif any(cat in ["technical", "code", "coding"] for cat in categories):
            return "Technical Content"
        elif any(
            cat in ["content_type", "content", "legal", "compliance"]
            for cat in categories
        ):
            return "Content Type"
        elif any(cat in ["presentations", "visual"] for cat in categories):
            return "Presentation Style"
        else:
            return categories[0].title() if categories else "General"

    @tool
    def recommend_style_tool(
        self,
        presentation_topic: str,
        audience: str = "general",
        context: str = "business",
    ) -> str:
        """Get intelligent style recommendations based on topic, audience, and learned preferences

        Args:
            presentation_topic: Topic or title of the presentation
            audience: Target audience (executives, technical, academic, general)
            context: Context or setting (business, conference, classroom, creative)

        Returns:
            Personalized style recommendations with explanations
        """
        try:
            # Get user preferences first
            preference_memories = self.memory_session.search_long_term_memories(
                query=f"{presentation_topic} {audience} {context}",
                namespace_prefix=f"slidedecks/user/{self.memory_session._actor_id}/style_preferences",
                top_k=3,
            )

            # Base recommendations on topic and audience
            recommendations = self._generate_base_recommendations(
                presentation_topic, audience, context
            )

            # Enhance with user preferences if available
            if preference_memories:
                user_preferences = self._extract_user_patterns(preference_memories)
                recommendations = self._personalize_recommendations(
                    recommendations, user_preferences
                )

                return f"""🎨 **Personalized Style Recommendations**

**For your "{presentation_topic}" presentation:**

{recommendations}

**Based on your preferences:**
{self._format_preference_insights(preference_memories)}

💡 **Why these recommendations:**
I've learned your style patterns and adapted these suggestions to match your proven preferences
while being appropriate for your {audience} audience in a {context} setting."""

            else:
                return f"""🎨 **Smart Style Recommendations**

**For your "{presentation_topic}" presentation:**

{recommendations}

💡 **Note**: These are general recommendations. As I learn your preferences through our interactions,
I'll provide increasingly personalized suggestions!

Try one of these styles and let me know what works well - I'll remember for next time."""

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return f"❌ Error generating recommendations: {str(e)}"

    def _generate_base_recommendations(
        self, topic: str, audience: str, context: str
    ) -> str:
        """Generate base style recommendations based on topic and context"""
        topic_lower = topic.lower()

        # Analyze topic for style cues
        if any(
            word in topic_lower for word in ["tech", "software", "data", "api", "code"]
        ):
            return """
**Presentation Type**: Tech
**Theme**: Modern with clean lines
**Colors**: Blue or purple for tech credibility
**Fonts**: Technical (JetBrains Mono) for headers, Modern (Inter) for content
**Style**: Minimal with focus on clarity and precision"""

        elif any(
            word in topic_lower
            for word in ["business", "strategy", "market", "finance"]
        ):
            return """
**Presentation Type**: Business
**Theme**: Professional and trustworthy
**Colors**: Blue or green for corporate appeal
**Fonts**: Modern (Inter) or Classic (Georgia) for readability
**Style**: Structured with elegant typography"""

        elif any(
            word in topic_lower
            for word in ["research", "study", "analysis", "academic"]
        ):
            return """
**Presentation Type**: Academic
**Theme**: Scholarly and readable
**Colors**: Classic blue or academic red
**Fonts**: Classic (Georgia) for traditional feel
**Style**: Clear hierarchy with detailed content support"""

        else:
            return """
**Presentation Type**: Creative
**Theme**: Engaging and memorable
**Colors**: Purple or green for visual interest
**Fonts**: Creative (Poppins) for modern appeal
**Style**: Dynamic with visual elements"""

    def _extract_user_patterns(self, memories: List[Dict]) -> Dict[str, Any]:
        """Extract patterns from user preference memories"""
        patterns = {
            "preferred_colors": [],
            "preferred_fonts": [],
            "preferred_types": [],
            "feedback_patterns": [],
        }

        for memory in memories:
            content = memory.get("content", {}).get("text", "").lower()

            # Extract color preferences
            for color in ["blue", "green", "purple", "red"]:
                if color in content and "prefer" in content:
                    patterns["preferred_colors"].append(color)

            # Extract font preferences
            for font in ["modern", "classic", "technical", "creative"]:
                if font in content:
                    patterns["preferred_fonts"].append(font)

            patterns["feedback_patterns"].append(content)

        return patterns

    def _personalize_recommendations(self, base_recs: str, user_patterns: Dict) -> str:
        """Personalize recommendations based on user patterns"""
        # This is a simplified version - could be much more sophisticated
        personalized = base_recs

        if user_patterns["preferred_colors"]:
            most_used_color = max(
                set(user_patterns["preferred_colors"]),
                key=user_patterns["preferred_colors"].count,
            )
            personalized += f"\\n**Personalized**: Using {most_used_color} (your preferred color scheme)"

        if user_patterns["preferred_fonts"]:
            most_used_font = max(
                set(user_patterns["preferred_fonts"]),
                key=user_patterns["preferred_fonts"].count,
            )
            personalized += f"\\n**Personalized**: Suggesting {most_used_font} fonts (matches your style)"

        return personalized

    def _format_preference_insights(self, memories: List[Dict]) -> str:
        """Format user preference insights"""
        if not memories:
            return "No preference history available yet."

        insights = []
        for memory in memories[:2]:  # Top 2 insights
            content = memory.get("content", {}).get("text", "")
            score = memory.get("score", 0)
            insights.append(f"- {content[:100]}... (confidence: {score:.1f})")

        return "\\n".join(insights)

    def _get_saved_preferences(self) -> Dict[str, Any]:
        """Get user preferences from memory - simple and reliable"""
        try:
            # Get preferences from memory
            prefs_json = self.get_user_preferences_tool("style preferences")
            prefs_data = json.loads(prefs_json)

            # Start with minimal defaults
            preferences = {}

            # Color mapping - scalable approach (ordered by specificity - longer phrases first)
            color_map = {
                # Dark colors (check specific phrases first)
                "dark navy blue": "dark-blue",
                "navy blue": "dark-blue",
                "dark blue": "dark-blue",
                "navy": "dark-blue",
                "dark background": "dark",
                "dark theme": "dark",
                "dark green": "dark-green",
                "dark purple": "dark-purple",
                "dark": "dark",
                "black": "black",
                "charcoal": "black",
                # Light/bright colors
                "light background": "blue",  # default light background
                "light blue": "blue",
                "sky blue": "blue",
                "bright blue": "blue",
                "cyan": "blue",
                "bright green": "green",
                "lime": "green",
                "teal": "green",
                "blue": "blue",
                "green": "green",
                "purple": "purple",
                "red": "red",
                "orange": "red",
            }

            # Extract preferences if they exist
            if prefs_data.get("status") == "established":
                for pref in prefs_data.get("preferences", []):
                    text = pref.get("preference", "").lower()

                    # Color preferences - pattern matching (checks longer phrases first)
                    for color_phrase, scheme in color_map.items():
                        if color_phrase in text:
                            preferences["color_scheme"] = scheme
                            break  # Use first match

                    # Gradient preferences
                    if "solid color" in text or "no gradient" in text:
                        preferences["use_gradients"] = False

                    # Shadow preferences
                    if "no shadow" in text or "minimal" in text:
                        preferences["use_shadows"] = False

                    # Font preferences
                    for font in ["modern", "classic", "technical", "creative"]:
                        if font in text:
                            preferences["font_family"] = font
                            break

            logger.info(f"🎨 Applied user preferences: {preferences}")
            return preferences

        except Exception as e:
            logger.error(f"Error getting preferences: {e}")
            return {}  # Return empty dict - let HTML generator use its defaults

    def _extract_style_from_request(self, user_request: str) -> Dict[str, Any]:
        """Programmatically extract styling preferences from user's original request text

        This approach doesn't rely on LLM interpretation - it searches for specific
        keywords in the user's natural language request.

        Args:
            user_request: The original user request text

        Returns:
            Dictionary of extracted style preferences
        """
        if not user_request:
            return {}

        request_lower = user_request.lower()
        explicit_prefs = {}

        # Gradient detection
        if "gradient" in request_lower:
            explicit_prefs["use_gradients"] = True
        if "solid color" in request_lower or "no gradient" in request_lower:
            explicit_prefs["use_gradients"] = False

        # Shadow detection
        if "no shadow" in request_lower:
            explicit_prefs["use_shadows"] = False

        # Background/color detection (ordered by specificity - check longer phrases first)
        style_keywords = {
            "light background": "blue",  # default light background
            "dark background": "dark",
            "dark pink": "dark-purple",
            "dark purple": "dark-purple",
            "dark blue": "dark-blue",
            "dark green": "dark-green",
            "navy blue": "dark-blue",
            "purple": "purple",
            "blue": "blue",
            "green": "green",
            "red": "red",
        }

        for phrase, scheme in style_keywords.items():
            if phrase in request_lower:
                explicit_prefs["color_scheme"] = scheme
                break  # Use first match (most specific due to ordering)

        # Font detection
        font_keywords = ["modern", "classic", "technical", "creative"]
        for font in font_keywords:
            if font in request_lower:
                explicit_prefs["font_family"] = font
                break

        logger.info(
            f"🔍 Extracted explicit preferences from user request: {explicit_prefs}"
        )
        return explicit_prefs

    def create_presentation(self, user_request: str) -> str:
        """Main entry point for creating presentations with automatic memory integration"""
        try:
            logger.info("🚀 Starting memory-enabled presentation creation...")
            logger.info(f"📝 User request: {user_request[:100]}...")

            # Simple approach: let the tool handle memory internally
            response = self.agent(user_request)
            result = str(response)

            logger.info("✅ Memory-enabled presentation creation completed")
            return result

        except Exception as e:
            logger.error(f"❌ Error in memory-enabled presentation creation: {e}")
            return f"❌ Sorry, I encountered an error: {
                str(e)
            }\\n\\nPlease try again or contact support if the issue persists."


# Example usage and demo functions
def create_memory_agent_demo(memory_session: MemorySession):
    """Create a demo of the memory-enabled slide agent"""

    logger.info("Creating memory-enabled slide deck agent...")
    agent = MemoryEnabledSlideDeckAgent(memory_session)

    # Demo request
    request = """I need a presentation about "AI Ethics in Healthcare" for a medical conference.
    The audience will be healthcare professionals and researchers.
    I prefer professional, trustworthy styling that's easy to read.

    Please create:
    - Title slide
    - What is AI Ethics section
    - Key ethical considerations (Privacy, Bias, Transparency, Accountability)
    - Healthcare-specific challenges
    - Best practices and recommendations
    - Q&A slide

    Make it look professional and credible for this important audience."""

    print("🤖 Memory-enabled agent processing request...")
    result = agent.create_presentation(request)
    print("✅ Result:", result)

    return agent, result


if __name__ == "__main__":
    print("Memory-enabled Slide Deck Agent")
    print("This agent requires a MemorySession - use with memory_setup.py")
    print("Example:")
    print("  from memory_setup import setup_slide_deck_memory")
    print("  memory, session_mgr, mgr = setup_slide_deck_memory()")
    print("  session = session_mgr.create_memory_session('user123', 'session456')")
    print("  agent = MemoryEnabledSlideDeckAgent(session)")
