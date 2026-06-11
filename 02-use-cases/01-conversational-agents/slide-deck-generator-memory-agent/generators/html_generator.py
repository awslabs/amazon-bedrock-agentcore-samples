"""
HTML slide generator for creating presentation slides
"""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import Environment

from .css_generator import AdvancedCSSGenerator, FontFamily, StylePreferences


class HTMLSlideGenerator:
    """Generates HTML slides from content and styling preferences"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.css_generator = AdvancedCSSGenerator()

    def process_markdown(self, text: str) -> str:
        """Convert basic markdown syntax to HTML"""
        if not text:
            return text

        # Process bold text: **text** -> <strong>text</strong>
        import re

        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)

        # Process italic text: *text* -> <em>text</em>
        text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)

        # Process inline code: `code` -> <code>code</code>
        text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)

        # Process line breaks: convert both \n and \\n to <br>
        text = text.replace("\n", "<br>").replace("\\n", "<br>")

        return text

    def create_slide_template(self) -> str:
        """Create the base HTML template for slides"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ presentation_title }}</title>
    <style>
        {{ css_content }}
    </style>
</head>
<body>
    <div class="presentation-container">
        {% for slide in slides %}
        <div class="slide" id="slide-{{ loop.index }}">
            {% if slide.type == 'title' %}
                <div class="slide-content title-slide">
                    <h1 class="main-title">{{ slide.title }}</h1>
                    {% if slide.subtitle %}
                    <h2 class="subtitle">{{ slide.subtitle }}</h2>
                    {% endif %}
                    {% if slide.author %}
                    <p class="author">{{ slide.author }}</p>
                    {% endif %}
                </div>
            {% elif slide.type == 'content' %}
                <div class="slide-content content-slide">
                    <h2 class="slide-title">{{ slide.title }}</h2>
                    <div class="slide-body">
                        {% if slide.bullet_points %}
                            <ul class="bullet-list">
                            {% for point in slide.bullet_points %}
                                <li>{{ point|safe }}</li>
                            {% endfor %}
                            </ul>
                        {% endif %}
                        {% if slide.content %}
                            <div class="slide-text">{{ slide.content|safe }}</div>
                        {% endif %}
                        {% if slide.image %}
                            <img src="{{ slide.image }}" alt="{{ slide.image_alt or 'Slide image' }}"
                                 class="slide-image">
                        {% endif %}
                    </div>
                </div>
            {% elif slide.type == 'section' %}
                <div class="slide-content section-slide">
                    <h1 class="section-title">{{ slide.title }}</h1>
                    {% if slide.subtitle %}
                    <h2 class="section-subtitle">{{ slide.subtitle }}</h2>
                    {% endif %}
                </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <!-- Navigation -->
    <div class="navigation">
        <button id="prevBtn" onclick="changeSlide(-1)">❮ Previous</button>
        <span id="slideNumber">1 / {{ slides|length }}</span>
        <button id="nextBtn" onclick="changeSlide(1)">Next ❯</button>
    </div>

    <script>
        let currentSlide = 1;
        const totalSlides = {{ slides|length }};

        function showSlide(n) {
            const slides = document.getElementsByClassName("slide");
            if (n > totalSlides) { currentSlide = 1; }
            if (n < 1) { currentSlide = totalSlides; }

            for (let i = 0; i < slides.length; i++) {
                slides[i].style.display = "none";
            }

            slides[currentSlide - 1].style.display = "block";
            document.getElementById("slideNumber").innerHTML = currentSlide + " / " + totalSlides;
        }

        function changeSlide(n) {
            showSlide(currentSlide += n);
        }

        // Initialize
        showSlide(currentSlide);

        // Keyboard navigation
        document.addEventListener('keydown', function(event) {
            if (event.key === 'ArrowRight' || event.key === ' ') {
                changeSlide(1);
            } else if (event.key === 'ArrowLeft') {
                changeSlide(-1);
            }
        });
    </script>
</body>
</html>
        """

    def create_style_preferences_from_params(
        self,
        theme: str = "professional",
        color_scheme: str = "blue",
        font_family: str = "modern",
        use_gradients: bool = False,
        use_shadows: bool = False,
        border_radius: int = 8,
        spacing_style: str = "comfortable",
        font_size_base: int = 16,
        header_style: str = "bold",
    ) -> StylePreferences:
        """Create StylePreferences object from simple parameters for backward compatibility"""

        font_mapping = {
            "modern": FontFamily.MODERN,
            "classic": FontFamily.CLASSIC,
            "technical": FontFamily.TECHNICAL,
            "creative": FontFamily.CREATIVE,
        }

        # Basic color schemes for backward compatibility
        color_schemes = {
            "blue": {
                "primary": "#2563eb",
                "secondary": "#3b82f6",
                "accent": "#0ea5e9",
                "background": "#f8fafc",
                "text": "#1e293b",
            },
            "green": {
                "primary": "#16a34a",
                "secondary": "#22c55e",
                "accent": "#10b981",
                "background": "#f0fdf4",
                "text": "#14532d",
            },
            "purple": {
                "primary": "#7c3aed",
                "secondary": "#8b5cf6",
                "accent": "#a855f7",
                "background": "#faf5ff",
                "text": "#581c87",
            },
            "red": {
                "primary": "#dc2626",
                "secondary": "#ef4444",
                "accent": "#f87171",
                "background": "#fef2f2",
                "text": "#7f1d1d",
            },
            # Dark color schemes for dark background preferences
            "dark": {
                "primary": "#3b82f6",
                "secondary": "#60a5fa",
                "accent": "#93c5fd",
                "background": "#0f172a",
                "text": "#f1f5f9",
            },
            "dark-blue": {
                "primary": "#3b82f6",
                "secondary": "#60a5fa",
                "accent": "#93c5fd",
                "background": "#1e293b",
                "text": "#f1f5f9",
            },
            "dark-green": {
                "primary": "#22c55e",
                "secondary": "#4ade80",
                "accent": "#86efac",
                "background": "#14532d",
                "text": "#f0fdf4",
            },
            "dark-purple": {
                "primary": "#a855f7",
                "secondary": "#c084fc",
                "accent": "#d8b4fe",
                "background": "#581c87",
                "text": "#faf5ff",
            },
            "black": {
                "primary": "#6b7280",
                "secondary": "#9ca3af",
                "accent": "#d1d5db",
                "background": "#111827",
                "text": "#f9fafb",
            },
        }

        colors = color_schemes.get(color_scheme, color_schemes["blue"])

        return StylePreferences(
            primary_color=colors["primary"],
            secondary_color=colors["secondary"],
            accent_color=colors["accent"],
            background_color=colors["background"],
            text_color=colors["text"],
            font_family=font_mapping.get(font_family, FontFamily.MODERN),
            header_style=header_style,
            use_gradients=use_gradients,
            use_shadows=use_shadows,
            border_radius=border_radius,
            spacing_style=spacing_style,
            font_size_base=font_size_base,
        )

    def parse_content_to_slides(
        self, content: str, title: str = "Presentation"
    ) -> List[Dict[str, Any]]:
        """Parse text content into slide structure"""
        slides = []
        lines = content.strip().split("\n")
        current_slide = None

        # Add title slide
        slides.append(
            {
                "type": "title",
                "title": title,
                "subtitle": "Generated Presentation",
                "author": f"Created on {datetime.now().strftime('%B %d, %Y')}",
            }
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for slide title (starts with #)
            if line.startswith("# "):
                if current_slide:
                    slides.append(current_slide)
                current_slide = {
                    "type": "content",
                    "title": line[2:].strip(),
                    "bullet_points": [],
                    "content": "",
                }
            # Check for section (starts with ##)
            elif line.startswith("## "):
                if current_slide:
                    slides.append(current_slide)
                slides.append({"type": "section", "title": line[3:].strip()})
                current_slide = None
            # Check for bullet point (starts with -)
            elif line.startswith("- "):
                if current_slide:
                    bullet_text = line[2:].strip()
                    # Process markdown in bullet points
                    bullet_text = self.process_markdown(bullet_text)
                    current_slide["bullet_points"].append(bullet_text)
            # Check for bullet point (starts with *)
            elif line.startswith("* "):
                if current_slide:
                    bullet_text = line[2:].strip()
                    # Process markdown in bullet points
                    bullet_text = self.process_markdown(bullet_text)
                    current_slide["bullet_points"].append(bullet_text)
            # Regular content
            else:
                if current_slide:
                    # Process markdown in content lines
                    processed_line = self.process_markdown(line)
                    if current_slide["content"]:
                        current_slide["content"] += "<br>" + processed_line
                    else:
                        current_slide["content"] = processed_line

        # Add the last slide (only if it has content)
        if current_slide and (
            (
                current_slide.get("bullet_points")
                and len(current_slide.get("bullet_points", [])) > 0
            )
            or (current_slide.get("content") and current_slide.get("content").strip())
        ):
            slides.append(current_slide)

        return slides

    def generate_presentation(
        self,
        content: str,
        title: str = "Presentation",
        theme: str = "professional",
        color_scheme: str = "blue",
        font_family: str = "modern",
        use_gradients: bool = False,
        use_shadows: bool = False,
        border_radius: int = 8,
        spacing_style: str = "comfortable",
        font_size_base: int = 16,
        header_style: str = "bold",
        preferences: Optional[StylePreferences] = None,
    ) -> str:
        """Generate complete HTML presentation with advanced styling"""

        # Parse content into slides
        slides = self.parse_content_to_slides(content, title)

        # Create or use provided style preferences
        if preferences is None:
            preferences = self.create_style_preferences_from_params(
                theme,
                color_scheme,
                font_family,
                use_gradients,
                use_shadows,
                border_radius,
                spacing_style,
                font_size_base,
                header_style,
            )

        # Generate advanced CSS
        css_content = self.css_generator.generate_advanced_css(preferences)

        # Create HTML from template with autoescape enabled
        env = Environment(autoescape=True)
        template = env.from_string(self.create_slide_template())
        html_content = template.render(
            presentation_title=title, slides=slides, css_content=css_content
        )

        # Save to file
        filename = f"{title.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.html"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return filepath
