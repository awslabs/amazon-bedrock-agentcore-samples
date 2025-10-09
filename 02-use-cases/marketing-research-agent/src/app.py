"""
AI Chat Assistant - Streamlit Web Interface

Simple AI chat interface with conversation capabilities.
"""

import streamlit as st
import requests
import json
import time
from uuid import uuid4
import os

# Page configuration
st.set_page_config(
    page_title="Marketing Researcher Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Simple CSS styling
st.markdown(
    """
<style>
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main container */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Chat container */
    .chat-container {
        background: white;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        min-height: 400px;
        margin-bottom: 1rem;
        padding: 1rem;
    }
    
    /* File list styling */
    .file-item {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .file-name {
        font-weight: 500;
        color: #111827;
        margin-bottom: 0.25rem;
    }
    
    .file-meta {
        font-size: 0.75rem;
        color: #6b7280;
    }
    
    /* Tool usage styling */
    .tool-usage {
        background: #f0f9ff;
        border: 1px solid #0ea5e9;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        margin: 0.25rem 0;
        font-size: 0.875rem;
        color: #0c4a6e;
        font-family: 'Monaco', 'Menlo', monospace;
    }
    
    .tool-icon {
        display: inline-block;
        margin-right: 0.5rem;
    }
    
    /* Report preview container */
    .report-preview {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_id" not in st.session_state:
        st.session_state.user_id = f"user_{uuid4().hex[:8]}"
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session_{uuid4().hex[:8]}"
    if "agent_url" not in st.session_state:
        st.session_state.agent_url = "http://localhost:8080/invocations"
    if "process_query" not in st.session_state:
        st.session_state.process_query = None
    if "show_preview" not in st.session_state:
        st.session_state.show_preview = None


def format_tool_usage(text):
    """Format tool usage information for better display"""
    import re

    # Tool usage patterns
    tool_patterns = [
        (r"Tool #(\d+): (\w+)", r"🔧 **Tool \1**: `\2`"),
        (
            r"INFO:bedrock_agentcore\.memory\.client:Created event: ([a-f0-9]+)#([a-f0-9]+)",
            r"📝 *Event created*",
        ),
        (r"╔═+.*═+╗", ""),  # Remove box drawing characters
        (r"║.*║", ""),
        (r"╚═+.*═+╝", ""),
        (r"╭─+.*─+╮", ""),
        (r"│.*│", ""),
        (r"╰─+.*─+╯", ""),
    ]

    formatted_text = text
    for pattern, replacement in tool_patterns:
        formatted_text = re.sub(
            pattern, replacement, formatted_text, flags=re.MULTILINE
        )

    # Clean up multiple newlines
    formatted_text = re.sub(r"\n\s*\n\s*\n", "\n\n", formatted_text)

    return formatted_text.strip()

def render_markdown_with_images(content, base_path="output"):
    """Render markdown content with proper image handling for Streamlit"""
    import re
    
    # Find all image references in markdown - handle both ./path and output/path patterns
    image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    
    # Split content by images to render them separately
    parts = re.split(image_pattern, content)
    
    i = 0
    while i < len(parts):
        # Render text part
        if parts[i].strip():
            st.markdown(parts[i])
        
        # Check if there's an image to render
        if i + 2 < len(parts):
            alt_text = parts[i + 1]
            image_path = parts[i + 2]
            
            # Handle different image path formats
            if image_path.startswith('./'):
                # Remove ./ prefix
                image_path = image_path[2:]
            
            # If path doesn't start with output/, prepend it
            if not image_path.startswith('output/'):
                if image_path.startswith('images/'):
                    full_image_path = os.path.join(base_path, image_path)
                else:
                    full_image_path = os.path.join(base_path, 'images', image_path)
            else:
                full_image_path = image_path
            
            # Render image if it exists
            if os.path.exists(full_image_path):
                st.image(full_image_path, caption=alt_text, use_container_width=True)
            else:
                st.warning(f"Image not found: {full_image_path}")
                st.info(f"Looking for: {full_image_path}")
            
            i += 3
        else:
            i += 1


def call_agent_api(prompt: str):
    """Call the agent API optimized for backend streaming pattern"""
    payload = {
        "input": {  # Wrap in input object
            "prompt": prompt,
        }
    }

    try:
        response = requests.post(
            st.session_state.agent_url, json=payload, stream=True, timeout=300
        )
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            if line and line.strip():
                line = line.strip()

                # Skip data: prefix and extract content
                if line.startswith("data: "):
                    content = line[6:]  # Remove 'data: ' prefix

                    # Remove quotes if present
                    if content.startswith('"') and content.endswith('"'):
                        content = content[1:-1]

                    # Unescape any escaped characters
                    content = content.replace('\\"', '"').replace("\\n", "\n")

                    # Only yield non-empty content
                    if content.strip():
                        yield content

                # Handle JSON responses (final response)
                elif line.startswith('{"role":'):
                    try:
                        json_data = json.loads(line)
                        if (
                            "content" in json_data
                            and len(json_data["content"]) > 0
                            and "text" in json_data["content"][0]
                        ):
                            final_text = json_data["content"][0]["text"]
                            yield final_text
                            return
                    except json.JSONDecodeError:
                        pass

    except requests.exceptions.RequestException as e:
        error_msg = f"Error connecting to agent: {str(e)}"
        yield error_msg


def parse_tool_tags(content):
    """Parse tool start/end tags and return structured data"""
    import re
    
    # Find tool start and end tags
    tool_start_pattern = r'<TOOL_START>(.*?)</TOOL_START>'
    tool_end_pattern = r'<TOOL_END>(.*?)</TOOL_END>'
    
    tool_starts = re.findall(tool_start_pattern, content)
    tool_ends = re.findall(tool_end_pattern, content)
    
    # Remove tool tags from content
    clean_content = re.sub(tool_start_pattern, '', content)
    clean_content = re.sub(tool_end_pattern, '', clean_content)
    
    return clean_content, tool_starts, tool_ends

def process_user_query(prompt: str):
    """Process user query with real-time streaming and simple tool handling"""
    if not prompt or len(prompt.strip()) == 0:
        st.error("Please enter a valid question.")
        return

    if len(prompt) > 10000:
        st.error("Your question is too long. Please keep it under 10,000 characters.")
        return

    with st.chat_message("assistant"):
        # Real-time streaming with simple tool detection
        buffer = ""
        text_placeholder = st.empty()
        current_text = ""
        processed_tools = set()
        
        try:
            for chunk in call_agent_api(prompt):
                if chunk:
                    buffer += chunk + "  \n"
                    
                    # Simple tool detection and replacement
                    import re
                    
                    # Check for complete tool tags
                    while '<TOOL_START>' in buffer and '</TOOL_START>' in buffer:
                        start_idx = buffer.find('<TOOL_START>')
                        end_idx = buffer.find('</TOOL_START>') + len('</TOOL_START>')
                        
                        # Add text before tool
                        text_before = buffer[:start_idx]
                        if text_before.strip():
                            current_text += text_before.strip() + " "
                        
                        # Extract tool info
                        tool_tag = buffer[start_idx:end_idx]
                        try:
                            tool_content = re.search(r'<TOOL_START>(.*?)</TOOL_START>', tool_tag)
                            if tool_content:
                                tool_data = json.loads(tool_content.group(1))
                                tool_id = tool_data.get('id', 'unknown')
                                
                                if tool_id not in processed_tools:
                                    processed_tools.add(tool_id)
                                    tool_name = tool_data.get('name', 'Unknown')
                                    tool_input = tool_data.get('input', {})
                                    
                                    # Create simple tool summary
                                    summary = tool_name
                                    if tool_input:
                                        for key in ['query', 'url', 'path', 'description']:
                                            if key in tool_input and tool_input[key]:
                                                value = str(tool_input[key])
                                                if len(value) > 50:
                                                    value = value[:50] + "..."
                                                summary += f": {value}"
                                                break
                                    
                                    # Add simple tool indicator to text
                                    current_text += f"\n\n🔧 **{summary}** ✅\n\n"
                        
                        except Exception as e:
                            # If tool parsing fails, just skip it
                            pass
                        
                        # Remove processed tool from buffer
                        buffer = buffer[end_idx:]
                    
                    # Update display with current text + remaining buffer
                    display_text = current_text
                    if buffer.strip():
                        # Only show clean text (no incomplete tool tags)
                        clean_buffer = re.sub(r'<TOOL_START>.*$', '', buffer)
                        if clean_buffer.strip():
                            display_text += clean_buffer.strip() + '\n'
                    
                    # Show with streaming cursor
                    text_placeholder.markdown(display_text + "▌")

            # Final display without cursor
            final_text = current_text + buffer
            # Clean up any remaining tool tags
            final_text = re.sub(r'<TOOL_START>.*?</TOOL_START>', '', final_text)
            
            if final_text.strip():
                text_placeholder.markdown(final_text.strip())
                
                # Clean version for session (remove tool indicators)
                clean_content = re.sub(r'🔧 \*\*.*?\*\* ✅', '', final_text)
                clean_content = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_content)
                
                st.session_state.messages.append(
                    {"role": "assistant", "content": clean_content.strip()}
                )
            else:
                error_msg = "I apologize, but I didn't receive a proper response. Please try again."
                text_placeholder.markdown(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )


def main():
    """Main application"""
    initialize_session_state()

    # Simple header
    st.title("Marketing Researcher Agent")

    # Sidebar
    with st.sidebar:
        st.header("Configuration")

        # Agent URL configuration
        new_url = st.text_input(
            "Agent URL",
            value=st.session_state.agent_url,
            help="URL of the AI Agent API",
        )
        if new_url != st.session_state.agent_url:
            st.session_state.agent_url = new_url

        # Session information
        st.subheader("Session Info")
        st.text(f"User ID: {st.session_state.user_id}")
        st.text(f"Session ID: {st.session_state.session_id}")

        # Reset session
        if st.button("New Session"):
            st.session_state.session_id = f"session_{uuid4().hex[:8]}"
            st.session_state.messages = []
            st.rerun()

        # Clear chat
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        # Generated Reports (only .md files)
        st.subheader("Generated Reports")
        output_dir = "output"
        reports_dir = os.path.join(output_dir, "reports")

        if os.path.exists(reports_dir):
            # Filter only .md files
            md_files = [
                f
                for f in os.listdir(reports_dir)
                if f.endswith(".md") and os.path.isfile(os.path.join(reports_dir, f))
            ]

            if md_files:
                st.write(f"{len(md_files)} report(s) available")

                for file in sorted(
                    md_files,
                    key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)),
                    reverse=True,
                ):
                    file_path = os.path.join(reports_dir, file)
                    file_size = os.path.getsize(file_path)
                    file_time = os.path.getmtime(file_path)

                    # Format file size
                    if file_size < 1024:
                        size_str = f"{file_size} B"
                    elif file_size < 1024 * 1024:
                        size_str = f"{file_size / 1024:.1f} KB"
                    else:
                        size_str = f"{file_size / (1024 * 1024):.1f} MB"

                    # Format time
                    import datetime

                    time_str = datetime.datetime.fromtimestamp(file_time).strftime(
                        "%m/%d %H:%M"
                    )

                    # Create file item
                    st.markdown(
                        f"""
                    <div class="file-item">
                        <div class="file-name">{file}</div>
                        <div class="file-meta">Report • {size_str} • {time_str}</div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

                    col1, col2 = st.columns([1, 1])

                    with col1:
                        # Preview button - now shows in main area
                        if st.button(
                            "Preview", key=f"preview_{file}", use_container_width=True
                        ):
                            st.session_state.show_preview = file
                            st.rerun()

                    with col2:
                        # Download button
                        try:
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    label="Download",
                                    data=f.read(),
                                    file_name=file,
                                    mime="text/markdown",
                                    key=f"download_{file}",
                                    use_container_width=True,
                                )
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

                # Clear all files button
                if st.button("Clear All Reports", use_container_width=True):
                    try:
                        for file in md_files:
                            os.remove(os.path.join(reports_dir, file))
                        st.success("All reports cleared!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error clearing files: {str(e)}")
            else:
                st.info("No reports generated yet.")
        else:
            st.info("Output directory will be created when reports are generated.")

        st.divider()

        # Example prompts
        st.subheader("Example Prompts")
        example_queries = [
            "Analyze current market trends in sustainable fashion",
            "Research competitor pricing strategies in SaaS",
            "Generate customer segmentation analysis",
            "Create market analysis report for this year",
            "Study consumer behavior in e-commerce",
        ]

        for i, query in enumerate(example_queries):
            if st.button(query, key=f"example_{i}", use_container_width=True):
                st.session_state.process_query = query
                st.rerun()

    # Check if we should show a report preview in main area
    if st.session_state.get("show_preview"):
        file_to_preview = st.session_state.show_preview
        output_dir = "output"
        reports_dir = os.path.join(output_dir, "reports")
        file_path = os.path.join(reports_dir, file_to_preview)

        if os.path.exists(file_path):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.subheader(f"📄 Report Preview: {file_to_preview}")
            with col2:
                if st.button("Close Preview", use_container_width=True):
                    st.session_state.show_preview = None
                    st.rerun()

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Show preview in a scrollable Streamlit container with proper image rendering
                with st.container(height=800):
                    render_markdown_with_images(content, "output")

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
        else:
            st.error("File not found")
            st.session_state.show_preview = None

        st.divider()

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Check if there's a query to process from example buttons
    if st.session_state.get("process_query"):
        prompt = st.session_state.process_query
        st.session_state.process_query = None  # Clear the flag

        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Process the query
        process_user_query(prompt)
        st.rerun()  # Refresh to show the new message

    # Chat input
    elif prompt := st.chat_input("Type your message here..."):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Process the query
        process_user_query(prompt)


if __name__ == "__main__":
    main()