"""
Advanced CSS generator for dynamic presentation styling based on user preferences
"""

from typing import Dict
from dataclasses import dataclass
from enum import Enum


class FontFamily(Enum):
    MODERN = "modern"
    CLASSIC = "classic"
    TECHNICAL = "technical"
    CREATIVE = "creative"


@dataclass
class StylePreferences:
    """Data class for user style preferences"""

    primary_color: str = "#2563eb"
    secondary_color: str = "#3b82f6"
    accent_color: str = "#0ea5e9"
    background_color: str = "#f8fafc"
    text_color: str = "#1e293b"
    font_family: FontFamily = FontFamily.MODERN
    font_size_base: int = 16
    slide_transition: str = "fade"
    use_gradients: bool = True
    use_shadows: bool = True
    border_radius: int = 8
    spacing_style: str = "comfortable"  # compact, comfortable, spacious
    header_style: str = "bold"  # bold, elegant, minimal


class AdvancedCSSGenerator:
    """Advanced CSS generator with user preference support"""

    def __init__(self):
        self.font_families = {
            FontFamily.MODERN: {
                "primary": "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
                "heading": "'Inter', sans-serif",
                "body": "'Inter', sans-serif",
            },
            FontFamily.CLASSIC: {
                "primary": "'Georgia', 'Times New Roman', Times, serif",
                "heading": "'Georgia', serif",
                "body": "'Georgia', serif",
            },
            FontFamily.TECHNICAL: {
                "primary": "'JetBrains Mono', 'Consolas', 'Monaco', monospace",
                "heading": "'JetBrains Mono', monospace",
                "body": "'System UI', sans-serif",
            },
            FontFamily.CREATIVE: {
                "primary": "'Poppins', 'Montserrat', sans-serif",
                "heading": "'Poppins', sans-serif",
                "body": "'Open Sans', sans-serif",
            },
        }

    def get_spacing_values(self, style: str) -> Dict[str, str]:
        """Get spacing values based on style preference"""
        spacing_configs = {
            "compact": {
                "slide_padding": "40px",
                "section_margin": "20px",
                "element_margin": "10px",
                "line_height": "1.4",
            },
            "comfortable": {
                "slide_padding": "60px",
                "section_margin": "30px",
                "element_margin": "20px",
                "line_height": "1.6",
            },
            "spacious": {
                "slide_padding": "80px",
                "section_margin": "40px",
                "element_margin": "30px",
                "line_height": "1.8",
            },
        }
        return spacing_configs.get(style, spacing_configs["comfortable"])

    def generate_gradient_background(self, preferences: StylePreferences) -> str:
        """Generate gradient background based on preferences"""
        if not preferences.use_gradients:
            return preferences.background_color

        # Create gradient using theme colors instead of hardcoded white
        return f"linear-gradient(135deg, {preferences.background_color} 0%, {
            self.adjust_color_brightness(preferences.background_color, 1.1)
        } 50%, {preferences.primary_color} 100%)"

    def adjust_color_brightness(self, hex_color: str, factor: float) -> str:
        """Adjust color brightness by a factor"""
        # Remove # if present
        hex_color = hex_color.lstrip("#")

        # Convert to RGB
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        # Adjust brightness
        adjusted = tuple(min(255, max(0, int(c * factor))) for c in rgb)

        # Convert back to hex
        return f"#{adjusted[0]:02x}{adjusted[1]:02x}{adjusted[2]:02x}"

    def hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex color to RGB string"""
        hex_color = hex_color.lstrip("#")
        return f"{int(hex_color[:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:], 16)}"

    def generate_advanced_css(self, preferences: StylePreferences) -> str:
        """Generate advanced CSS based on user preferences"""

        # Get font family configuration
        fonts = self.font_families[preferences.font_family]
        spacing = self.get_spacing_values(preferences.spacing_style)
        background = self.generate_gradient_background(preferences)

        # Shadow styles
        box_shadow = (
            "0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)"
            if preferences.use_shadows
            else "none"
        )
        text_shadow = (
            "0 1px 2px rgba(0, 0, 0, 0.1)" if preferences.use_shadows else "none"
        )

        css = f"""
        /* Advanced CSS Generated with User Preferences */
        /* Font Family: {preferences.font_family.value} */

        :root {{
            --primary-color: {preferences.primary_color};
            --secondary-color: {preferences.secondary_color};
            --accent-color: {preferences.accent_color};
            --background-color: {preferences.background_color};
            --text-color: {preferences.text_color};
            --border-radius: {preferences.border_radius}px;
            --box-shadow: {box_shadow};
            --text-shadow: {text_shadow};
            --slide-padding: {spacing["slide_padding"]};
            --section-margin: {spacing["section_margin"]};
            --element-margin: {spacing["element_margin"]};
            --line-height: {spacing["line_height"]};
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: {fonts["primary"]};
            font-size: {preferences.font_size_base}px;
            background: {background};
            color: var(--text-color);
            overflow: hidden;
            line-height: var(--line-height);
        }}

        .presentation-container {{
            width: 100vw;
            height: 100vh;
            position: relative;
        }}

        .slide {{
            display: none;
            width: 100%;
            height: 100vh;
            padding: var(--slide-padding);
            position: relative;
        }}

        .slide:first-child {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .slide-content {{
            max-width: 1000px;
            width: 100%;
            margin: 0 auto;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        /* Title Slide Styles */
        .title-slide {{
            text-align: center;
            align-items: center;
        }}

        .title-slide .main-title {{
            font-family: {fonts["heading"]};
            font-size: {preferences.font_size_base * 2.5}px;
            font-weight: {self.get_header_weight(preferences.header_style)};
            color: var(--primary-color);
            margin-bottom: var(--element-margin);
            text-shadow: var(--text-shadow);
            {self.get_title_decoration(preferences)}
        }}

        .title-slide .subtitle {{
            font-size: {preferences.font_size_base * 1.5}px;
            color: var(--secondary-color);
            margin-bottom: var(--section-margin);
            font-weight: 300;
        }}

        .title-slide .author {{
            font-size: {preferences.font_size_base * 1.1}px;
            color: var(--text-color);
            opacity: 0.8;
        }}

        /* Content Slide Styles */
        .content-slide {{
            text-align: left;
        }}

        .content-slide .slide-title {{
            font-family: {fonts["heading"]};
            font-size: {preferences.font_size_base * 2}px;
            color: var(--primary-color);
            margin-bottom: var(--section-margin);
            font-weight: {self.get_header_weight(preferences.header_style)};
            {self.get_header_decoration(preferences)}
        }}

        .slide-body {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .bullet-list {{
            font-size: {preferences.font_size_base * 1.2}px;
            line-height: var(--line-height);
            list-style-type: none;
            padding-left: 0;
        }}

        .bullet-list li {{
            margin-bottom: var(--element-margin);
            position: relative;
            padding-left: 40px;
            {self.get_list_animation("business")}
        }}

        .bullet-list li:before {{
            content: "{self.get_bullet_style("business")}";
            color: var(--accent-color);
            font-size: {preferences.font_size_base * 1.3}px;
            position: absolute;
            left: 0;
            top: 0;
        }}

        .slide-text {{
            font-size: {preferences.font_size_base * 1.2}px;
            line-height: var(--line-height);
            margin-bottom: var(--element-margin);
            font-family: {fonts["body"]};
        }}

        .slide-image {{
            max-width: 100%;
            height: auto;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            margin: var(--element-margin) 0;
        }}

        /* Section Slide Styles */
        .section-slide {{
            text-align: center;
            align-items: center;
        }}

        .section-slide .section-title {{
            font-family: {fonts["heading"]};
            font-size: {preferences.font_size_base * 3}px;
            color: var(--primary-color);
            font-weight: {self.get_header_weight(preferences.header_style)};
            margin-bottom: var(--element-margin);
            text-shadow: var(--text-shadow);
        }}

        .section-slide .section-subtitle {{
            font-size: {preferences.font_size_base * 1.8}px;
            color: var(--secondary-color);
            font-weight: 300;
        }}

        /* Navigation Styles */
        .navigation {{
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba({self.hex_to_rgb(preferences.background_color)}, 0.95);
            padding: 15px 25px;
            border-radius: calc(var(--border-radius) * 3);
            box-shadow: var(--box-shadow);
            display: flex;
            align-items: center;
            gap: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba({self.hex_to_rgb(preferences.background_color)}, 0.2);
        }}

        .navigation button {{
            background: var(--primary-color);
            color: {preferences.background_color};
            border: 1px solid {preferences.text_color};
            padding: 12px 18px;
            border-radius: var(--border-radius);
            cursor: pointer;
            font-size: {preferences.font_size_base * 0.9}px;
            transition: all 0.3s ease;
            font-family: {fonts["primary"]};
        }}

        .navigation button:hover {{
            background: var(--secondary-color);
            transform: translateY(-1px);
            box-shadow: var(--box-shadow);
        }}

        .navigation button:disabled {{
            background: {preferences.text_color};
            color: {preferences.background_color};
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}

        #slideNumber {{
            font-weight: 600;
            color: {preferences.text_color};
            min-width: 60px;
            font-family: {fonts["primary"]};
        }}

        /* Presentation Type Specific Styles */
        {self.get_type_specific_styles("business", preferences)}

        /* Animations and Transitions */
        .slide {{
            transition: all 0.5s ease-in-out;
        }}

        .slide-content > * {{
            animation: slideInUp 0.6s ease-out;
        }}

        @keyframes slideInUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        /* Responsive Design */
        @media (max-width: 768px) {{
            .slide {{
                padding: calc(var(--slide-padding) * 0.6);
            }}

            .title-slide .main-title {{
                font-size: {preferences.font_size_base * 2}px;
            }}

            .content-slide .slide-title {{
                font-size: {preferences.font_size_base * 1.6}px;
            }}

            .bullet-list {{
                font-size: {preferences.font_size_base * 1.1}px;
            }}
        }}
        """

        return css

    def get_header_weight(self, style: str) -> str:
        """Get font weight based on header style"""
        weights = {"bold": "700", "elegant": "400", "minimal": "300"}
        return weights.get(style, "600")

    def get_title_decoration(self, preferences: StylePreferences) -> str:
        """Get title decoration based on presentation type and style"""
        # Simplified - no presentation type logic
        return ""

    def get_header_decoration(self, preferences: StylePreferences) -> str:
        """Get header decoration for content slides"""
        # Simplified - no presentation type logic
        return ""

    def get_bullet_style(self, presentation_type: str = "business") -> str:
        """Get bullet point style based on presentation type"""
        styles = {"tech": "▶", "business": "●", "academic": "■", "creative": "★"}
        return styles.get(presentation_type, "●")

    def get_list_animation(self, presentation_type: str = "business") -> str:
        """Get list item animation based on presentation type"""
        if presentation_type == "creative":
            return "transition: transform 0.2s ease; cursor: default;"
        return ""

    def get_type_specific_styles(
        self, presentation_type: str = "business", preferences: StylePreferences = None
    ) -> str:
        """Get presentation type-specific CSS styles"""
        if not preferences:
            return ""

        if presentation_type == "tech":
            return f"""
            .code-block {{
                background: #1e293b;
                color: #e2e8f0;
                padding: 20px;
                border-radius: var(--border-radius);
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                margin: var(--element-margin) 0;
                border-left: 4px solid {preferences.accent_color};
            }}

            .tech-highlight {{
                background: linear-gradient(90deg, {preferences.accent_color}20, transparent);
                padding: 10px;
                border-radius: var(--border-radius);
                border-left: 3px solid {preferences.accent_color};
            }}
            """
        elif presentation_type == "creative":
            return f"""
            .creative-accent {{
                background: linear-gradient(45deg, {preferences.primary_color}, {preferences.accent_color});
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .bullet-list li:hover {{
                transform: translateX(10px);
                color: {preferences.accent_color};
            }}
            """
        elif presentation_type == "academic":
            return f"""
            .citation {{
                font-style: italic;
                font-size: {preferences.font_size_base * 0.9}px;
                color: {self.adjust_color_brightness(preferences.text_color, 0.7)};
                margin-top: 10px;
            }}

            .academic-note {{
                background: {preferences.background_color};
                border: 1px solid {preferences.secondary_color};
                padding: 15px;
                border-radius: var(--border-radius);
                margin: var(--element-margin) 0;
            }}
            """
        return ""
