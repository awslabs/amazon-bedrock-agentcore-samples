"""
Basic slide deck agent without memory capabilities
"""

import logging
import os
import sys

from config import OUTPUT_DIR
from generators.html_generator import HTMLSlideGenerator
from strands import Agent, tool

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


logger = logging.getLogger(__name__)


class BasicSlideDeckAgent:
    """Agent for creating slide decks without memory capabilities"""

    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        self.html_generator = HTMLSlideGenerator(output_dir)

        # Create the Strands agent with tools
        self.agent = Agent(
            model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            tools=[self.create_slides_tool, self.get_presentation_info],
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the basic agent"""
        return """You are a helpful slide deck creation assistant.
You help users create professional presentations by generating structured content and HTML slides.

Your capabilities:
1. Create slide content from user descriptions
2. Generate HTML presentations with professional styling
3. Organize content into logical slide sequences
4. Apply basic themes and color schemes

When creating presentations:
- Start with a title slide
- Use clear, concise slide titles
- Organize content into bullet points when appropriate
- Create section slides for major topics
- Ensure logical flow between slides

Available themes: professional, modern, minimal
Available color schemes: blue, green, purple, red

Format content using:
- # Slide Title (for content slides)
- ## Section Title (for section divider slides)
- - Bullet point (for list items)
- Regular text for paragraphs

Always use the create_slides_tool to generate the actual HTML presentation."""

    @tool
    def create_slides_tool(
        self,
        content: str,
        title: str,
        theme: str = "professional",
        color_scheme: str = "blue",
    ) -> str:
        """Create HTML slides from structured content

        Args:
            content: Slide content in markdown format:
                    # Slide Title
                    - Bullet point 1
                    - Bullet point 2

                    Use # for each new slide title, then add bullet points with - or *
            title: Presentation title
            theme: Visual theme (professional, modern, minimal)
            color_scheme: Color scheme (blue, green, purple, red)

        Returns:
            File path to generated HTML presentation
        """
        try:
            # Validate inputs
            valid_themes = ["professional", "modern", "minimal"]
            valid_colors = ["blue", "green", "purple", "red"]

            if theme not in valid_themes:
                theme = "professional"
            if color_scheme not in valid_colors:
                color_scheme = "blue"

            # Generate the presentation
            filepath = self.html_generator.generate_presentation(
                content=content, title=title, theme=theme, color_scheme=color_scheme
            )

            logger.info(f"Generated presentation: {filepath}")
            return f"Presentation created successfully: {os.path.basename(filepath)}\\nFull path: {filepath}"

        except Exception as e:
            logger.error(f"Error creating slides: {e}")
            return f"Error creating presentation: {str(e)}"

    @tool
    def get_presentation_info(self) -> str:
        """Get information about available themes and options

        Returns:
            Information about available presentation options
        """
        return """Available Presentation Options:

THEMES:
- professional: Clean, business-appropriate design
- modern: Contemporary styling with bold elements
- minimal: Simple, focused design

COLOR SCHEMES:
- blue: Professional blue tones
- green: Fresh, natural green palette
- purple: Creative, modern purple theme
- red: Bold, attention-grabbing red scheme

CONTENT FORMATTING:
- Use '# Title' for slide titles
- Use '## Section' for section dividers
- Use '- Point' for bullet points
- Write paragraphs as regular text

The agent will automatically create a title slide and organize your content into a logical presentation flow."""

    def create_presentation(self, user_request: str) -> str:
        """Create a presentation based on user request"""
        try:
            response = self.agent(user_request)
            return str(response)  # Convert AgentResult to string
        except Exception as e:
            logger.error(f"Error in presentation creation: {e}")
            return f"Sorry, I encountered an error: {str(e)}"


def demo_basic_agent():
    """Demonstrate the basic agent functionality"""
    agent = BasicSlideDeckAgent()

    # Example request
    request = """Create a 5-slide presentation about "Introduction to AI" with:
    - Title slide
    - What is AI section
    - Types of AI (Machine Learning, Deep Learning, NLP)
    - Applications of AI (Healthcare, Finance, Transportation)
    - Future of AI

    Use a blue color scheme and professional theme."""

    print("Creating presentation with basic agent...")
    result = agent.create_presentation(request)
    print(result)
    return result


if __name__ == "__main__":
    demo_basic_agent()
