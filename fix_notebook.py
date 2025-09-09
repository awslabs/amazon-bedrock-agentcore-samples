#!/usr/bin/env python3
import json
import sys

def fix_parse_event_function(notebook_path):
    """Fix the parse_event function in the notebook"""
    
    # Read the notebook
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    # Find the cell with parse_event function
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code' and any('def parse_event' in line for line in cell['source']):
            # Find the lines to replace
            source_lines = cell['source']
            
            # Find start and end of parse_event function
            start_idx = None
            end_idx = None
            
            for i, line in enumerate(source_lines):
                if 'def parse_event(event):' in line:
                    start_idx = i
                elif start_idx is not None and line.strip() == '' and i > start_idx + 10:
                    # Look for the end of the function (empty line after return statement)
                    if i > 0 and 'return ""' in source_lines[i-1]:
                        end_idx = i
                        break
            
            if start_idx is not None and end_idx is not None:
                # Replace the parse_event function
                new_function = [
                    "def parse_event(event):\n",
                    "    \"\"\"\n",
                    "    Simplified event parser that handles streaming events more robustly\n",
                    "    \"\"\"\n",
                    "    try:\n",
                    "        # Skip initialization events\n",
                    "        if any(key in event for key in ['init_event_loop', 'start', 'start_event_loop']):\n",
                    "            return \"\"\n",
                    "        \n",
                    "        # Handle direct data events\n",
                    "        if 'data' in event and isinstance(event['data'], str):\n",
                    "            return event['data']\n",
                    "        \n",
                    "        # Handle Bedrock streaming events\n",
                    "        if 'event' in event:\n",
                    "            event_data = event['event']\n",
                    "            \n",
                    "            # Tool execution start\n",
                    "            if 'contentBlockStart' in event_data:\n",
                    "                start_data = event_data['contentBlockStart'].get('start', {})\n",
                    "                if 'toolUse' in start_data:\n",
                    "                    tool_name = start_data['toolUse'].get('name', 'unknown_tool')\n",
                    "                    return f\"\\\\n\\\\n[Executing: {tool_name}]\\\\n\\\\n\"\n",
                    "            \n",
                    "            # Text content delta\n",
                    "            if 'contentBlockDelta' in event_data:\n",
                    "                delta = event_data['contentBlockDelta'].get('delta', {})\n",
                    "                if 'text' in delta:\n",
                    "                    return delta['text']\n",
                    "            \n",
                    "            # Message delta\n",
                    "            if 'messageDelta' in event_data:\n",
                    "                delta = event_data['messageDelta'].get('delta', {})\n",
                    "                if 'text' in delta:\n",
                    "                    return delta['text']\n",
                    "        \n",
                    "        # Fallback: try to extract any text content\n",
                    "        if isinstance(event, dict):\n",
                    "            if 'text' in event:\n",
                    "                return event['text']\n",
                    "            if 'content' in event and isinstance(event['content'], str):\n",
                    "                return event['content']\n",
                    "        \n",
                    "        return \"\"\n",
                    "        \n",
                    "    except Exception as e:\n",
                    "        # Log the error but don't break the stream\n",
                    "        print(f\"Error parsing event: {e}\")\n",
                    "        return \"\"\n",
                    "\n"
                ]
                
                # Replace the old function with the new one
                cell['source'] = source_lines[:start_idx] + new_function + source_lines[end_idx:]
                
                print(f"Fixed parse_event function in notebook")
                break
    
    # Write the updated notebook
    with open(notebook_path, 'w') as f:
        json.dump(notebook, f, indent=1)
    
    print(f"Updated notebook saved to {notebook_path}")

if __name__ == "__main__":
    notebook_path = "/Users/omrsamer/Desktop/VSCode/amazon-bedrock-agentcore-samples/01-tutorials/01-AgentCore-runtime/03-advanced-concepts/05-multi-agents/01-multi-runtimes-with-boto3/distributed_agents_with_agentcore.ipynb"
    fix_parse_event_function(notebook_path)
