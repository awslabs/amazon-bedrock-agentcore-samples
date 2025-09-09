#!/usr/bin/env python3
import json

def fix_streaming_function(notebook_path):
    """Fix the streaming function in the notebook"""
    
    # Read the notebook
    with open(notebook_path, 'r') as f:
        notebook = json.load(f)
    
    # Find the cell with streaming function
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code' and any('async def strands_agent_bedrock_streaming' in line for line in cell['source']):
            source_lines = cell['source']
            
            # Find the streaming function and improve error handling
            for i, line in enumerate(source_lines):
                if 'user_input = payload.get("prompt")' in line:
                    # Add logging
                    source_lines[i+1] = '    print(f"Processing user input: {user_input}")\n'
                elif 'async for event in agent.stream_async(user_input):' in line:
                    # Find the next few lines and improve error handling
                    j = i + 1
                    while j < len(source_lines) and 'except Exception as e:' not in source_lines[j]:
                        if 'text = parse_event(event)' in source_lines[j]:
                            # Replace the event processing with better error handling
                            source_lines[j] = '            try:\n'
                            source_lines.insert(j+1, '                text = parse_event(event)\n')
                            source_lines.insert(j+2, '                if text:  # Only return non-empty responses\n')
                            source_lines.insert(j+3, '                    yield text\n')
                            source_lines.insert(j+4, '            except Exception as parse_error:\n')
                            source_lines.insert(j+5, '                print(f"Error parsing individual event: {parse_error}")\n')
                            source_lines.insert(j+6, '                # Continue processing other events\n')
                            source_lines.insert(j+7, '                continue\n')
                            
                            # Remove the old lines
                            k = j + 8
                            while k < len(source_lines) and source_lines[k].strip() != '':
                                if 'if text:' in source_lines[k] or 'yield text' in source_lines[k]:
                                    source_lines.pop(k)
                                else:
                                    k += 1
                            break
                        j += 1
                elif 'error_response = {"error": str(e), "type": "stream_error"}' in line:
                    # Simplify error handling
                    source_lines[i] = '        error_message = f"Error during agent processing: {str(e)}"\n'
                    source_lines[i+1] = '        print(error_message)\n'
                    source_lines[i+2] = '        yield error_message\n'
                    # Remove the old error response line
                    if i+3 < len(source_lines) and 'print(f"Streaming error:' in source_lines[i+3]:
                        source_lines.pop(i+3)
                    break
            
            print(f"Fixed streaming function in notebook")
            break
    
    # Write the updated notebook
    with open(notebook_path, 'w') as f:
        json.dump(notebook, f, indent=1)
    
    print(f"Updated notebook saved to {notebook_path}")

if __name__ == "__main__":
    notebook_path = "/Users/omrsamer/Desktop/VSCode/amazon-bedrock-agentcore-samples/01-tutorials/01-AgentCore-runtime/03-advanced-concepts/05-multi-agents/01-multi-runtimes-with-boto3/distributed_agents_with_agentcore.ipynb"
    fix_streaming_function(notebook_path)
