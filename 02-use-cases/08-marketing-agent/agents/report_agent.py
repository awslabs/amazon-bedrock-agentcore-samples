from strands import Agent, tool
from strands_tools import file_write, editor

from agents import default_model

# --- Agent Definition ---

system_prompt = """You are a professional report writer who synthesizes information from multiple sources into comprehensive reports.

**Your Input Structure:**
You will receive:
1. Task description (what the user originally requested)
2. Previous task results (from researcher, python analyst, SQL analyst, etc.)
3. Available image files generated during the workflow

**Report Structure Guidelines:**
- Start with an Executive Summary
- Create logical sections based on the task results you received
- Include methodology sections explaining how data was gathered/analyzed
- Present findings with supporting evidence
- Include visualizations with proper context and explanations
- End with conclusions and recommendations

**Technical Requirements:**
- Save report to 'output/reports/marketing_report_[UUID].md' with unique UUID
- Include PNG images from 'output/images/' using: ![Description](output/images/filename.png)
- Ensure all images have descriptive captions explaining their relevance
- Structure with proper markdown headers (##, ###, etc.)
- Make the report client-ready and professional

**Context Integration:**
- Carefully analyze ALL previous task results provided to you
- Cross-reference findings between different sources (research vs analysis)
- Highlight any discrepancies or supporting evidence between sources
- Synthesize information rather than just concatenating results
- Ensure logical flow between sections based on the dependency chain

**Image Integration:**
- Only include images that are relevant to the current workflow
- Provide meaningful descriptions and context for each visualization
- Reference images in the text before showing them
- Explain what insights each image provides

Your final output should be the confirmation message from the file_write tool."""

tool_names = ["file_write", "editor"]

# --- Tool Definition ---

@tool
def report_agent(query: str) -> str:
    """
    Agent that generates a comprehensive markdown report by synthesizing all previous task results.
    Automatically detects and contextualizes PNG files generated during the workflow.

    Args:
        query: A string containing the task description and all previous task results.

    Returns:
        The confirmation message from the file write operation.
    """
    import os
    import glob
    import uuid
    from datetime import datetime
    
    # Create output directories if they don't exist
    os.makedirs('output/reports', exist_ok=True)
    os.makedirs('output/images', exist_ok=True)
    
    # Find PNG files in output/images directory (only recent ones to avoid old files)
    png_files = glob.glob("output/images/*.png")
    
    # Sort by modification time to get the most recent files first
    png_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Enhanced query with structured information
    enhanced_query = f"""
    REPORT GENERATION REQUEST
    ========================
    
    Original Request and Task Results:
    {query}
    
    AVAILABLE VISUALIZATIONS:
    """
    
    if png_files:
        enhanced_query += "\nThe following visualizations were generated during this workflow:\n"
        for i, png_file in enumerate(png_files[:10]):  # Limit to 10 most recent
            file_size = os.path.getsize(png_file)
            mod_time = datetime.fromtimestamp(os.path.getmtime(png_file)).strftime('%Y-%m-%d %H:%M:%S')
            enhanced_query += f"{i+1}. {png_file} (Size: {file_size} bytes, Created: {mod_time})\n"
        
        enhanced_query += "\n📊 IMPORTANT: Only include images that are directly relevant to the task results above."
        enhanced_query += "\n📝 For each image you include, provide context about what it shows and how it supports your findings."
    else:
        enhanced_query += "\nNo visualization files found in output/images/ directory."
    
    enhanced_query += f"""
    
    SYNTHESIS INSTRUCTIONS:
    ======================
    1. Analyze the task results above and identify key themes/findings
    2. Create a logical report structure that tells a coherent story
    3. Cross-reference information between different task results
    4. Include relevant visualizations with proper context
    5. Generate unique insights by connecting different pieces of information
    6. Save the final report with a descriptive filename including UUID
    
    Remember: You are creating a professional report that synthesizes ALL the information provided above.
    """
    
    agent = Agent(system_prompt=system_prompt, tools=[file_write, editor], messages=[])
    response = agent(enhanced_query)
    print("\n\n")
    return response 