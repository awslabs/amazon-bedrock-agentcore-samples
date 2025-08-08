import json
import os
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import uuid
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError, ProfileNotFound
from botocore.config import Config
from contextlib import asynccontextmanager
import time
from functools import lru_cache

# Load environment variables
load_dotenv()

# Global cache for AWS session and agents
_aws_session_cache = None
_agents_cache = {}
_model_cache = {}

# Global variables for AWS session and region
aws_session = None
aws_region = None

@lru_cache(maxsize=1)
def get_aws_credentials():
    """Cached AWS credentials setup"""
    aws_profile = os.getenv('AWS_PROFILE', 'default')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    print("🔐 Setting up AWS credentials...")
    
    # Try AWS profile first
    try:
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        # Test the credentials
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Using AWS profile: {aws_profile}")
        print(f"   Account: {identity.get('Account', 'Unknown')}")
        print(f"   User/Role: {identity.get('Arn', 'Unknown').split('/')[-1]}")
        print(f"   Region: {aws_region}")
        
        # CRITICAL FIX: Set environment variables to match profile credentials
        # This ensures AgentCore uses the same credentials
        credentials = session.get_credentials()
        if credentials:
            os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if credentials.token:
                os.environ['AWS_SESSION_TOKEN'] = credentials.token
            else:
                # Remove session token if not present to avoid conflicts
                os.environ.pop('AWS_SESSION_TOKEN', None)
            os.environ['AWS_DEFAULT_REGION'] = aws_region
            print("✅ Environment variables synchronized with profile credentials")
        
        return session, aws_region
        
    except ProfileNotFound:
        print(f"⚠️  AWS profile '{aws_profile}' not found, trying access keys...")
    except NoCredentialsError:
        print(f"⚠️  No credentials found for profile '{aws_profile}', trying access keys...")
    except Exception as e:
        print(f"⚠️  Profile authentication failed: {e}, trying access keys...")
    
    # Fallback to access keys (but warn about potential issues)
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    if aws_access_key and aws_secret_key:
        try:
            session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            # Test the credentials
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            print(f"✅ Using AWS access keys")
            print(f"   Account: {identity.get('Account', 'Unknown')}")
            print(f"   Access Key: {aws_access_key[:8]}...")
            print(f"   Region: {aws_region}")
            print("⚠️  Note: Using access keys - ensure AgentCore permissions are attached to this user")
            return session, aws_region
            
        except Exception as e:
            print(f"❌ Access key authentication failed: {e}")
            raise Exception(f"AWS authentication failed: {e}")
    else:
        print("❌ No AWS access keys found in environment variables")
        raise Exception("No AWS credentials available. Please configure AWS profile or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")

# Import strands-agents framework - handle both installed and local versions
try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    print("✓ Using strands-agents framework")
except ImportError:
    # Try to import from parent directory (local strands)
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strands_path = os.path.join(parent_dir, '..')
    if strands_path not in sys.path:
        sys.path.insert(0, strands_path)
    
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel
        print("✓ Using local strands framework")
    except ImportError as e:
        print(f"❌ Failed to import strands framework: {e}")
        print("Please ensure strands-agents is installed: pip install strands-agents")
        raise

# Import AgentCore for code interpreter
from bedrock_agentcore.tools.code_interpreter_client import code_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global aws_session, aws_region
    aws_session, aws_region = setup_aws_credentials()
    initialize_agents()
    yield
    # Shutdown (if needed)
    pass

app = FastAPI(
    title="AgentCore Code Interpreter", 
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class CodeGenerationRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None

class InteractiveCodeExecutionRequest(BaseModel):
    code: str
    session_id: Optional[str] = None
    inputs: Optional[List[str]] = None  # Pre-provided inputs for interactive code

class CodeExecutionRequest(BaseModel):
    code: str
    session_id: Optional[str] = None
    interactive: Optional[bool] = False
    inputs: Optional[List[str]] = None

class FileUploadRequest(BaseModel):
    filename: str
    content: str
    session_id: Optional[str] = None

# Session management
class CodeInterpreterSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.conversation_history = []
        self.code_history = []
        self.execution_results = []
        self.interactive_sessions = {}  # Track interactive execution sessions
        self.uploaded_csv = None  # Store uploaded CSV file data

# Global variables for agents
code_generator_agent = None
code_executor_agent = None
executor_type = "unknown"  # Track which executor type we're using
active_sessions = {}

def clean_output_for_display(output: str) -> str:
    """Clean output for display by removing image binary data while preserving analysis text"""
    if not output:
        return output
    
    # If output contains IMAGE_DATA, extract everything except the binary
    if 'IMAGE_DATA:' in output:
        parts = output.split('IMAGE_DATA:')
        cleaned_parts = []
        
        # Add the part before IMAGE_DATA
        if parts[0].strip():
            cleaned_parts.append(parts[0].strip())
        
        # Process parts after IMAGE_DATA
        for i in range(1, len(parts)):
            # Split on newline to separate binary from any following text
            lines = parts[i].split('\n', 1)
            if len(lines) > 1:
                # Skip the binary line, keep any text after it
                remaining_text = lines[1].strip()
                if remaining_text and not remaining_text.startswith(('iVBOR', '/9j/', 'data:')):
                    cleaned_parts.append(remaining_text)
        
        if cleaned_parts:
            result = '\n\n'.join(cleaned_parts)
            print(f"🧹 Cleaned output: removed image binary, kept {len(result)} chars of text")
            return result
        else:
            return "Code executed successfully - chart generated"
    
    return output

def extract_image_data(execution_result: str):
    """Extract base64 image data from execution results - fixed for AgentCore format"""
    try:
        import re
        import base64
        
        images = []
        
        print(f"🔍 Image extraction - Input length: {len(execution_result)}")
        print(f"🔍 Contains IMAGE_DATA: {'IMAGE_DATA:' in execution_result}")
        
        if 'IMAGE_DATA:' in execution_result:
            # Find all IMAGE_DATA: patterns in the text
            # AgentCore puts the full base64 string in stdout, so we need a greedy pattern
            pattern = r'IMAGE_DATA:([A-Za-z0-9+/=\n\r\s]+?)(?=\n[A-Za-z]|\nBase64|\n$|$)'
            matches = re.findall(pattern, execution_result, re.MULTILINE | re.DOTALL)
            
            print(f"🔍 Regex matches found: {len(matches)}")
            
            for i, match in enumerate(matches):
                try:
                    # Clean up the base64 string - remove all whitespace and newlines
                    clean_match = re.sub(r'[\s\n\r]', '', match)
                    
                    print(f"🔍 Match {i+1} - Original length: {len(match)}, Clean length: {len(clean_match)}")
                    print(f"🔍 Match {i+1} - Starts with: {clean_match[:50]}...")
                    
                    # Must be reasonable length for an image (at least 1KB when decoded)
                    if len(clean_match) > 1000:
                        # Validate it's valid base64 and can be decoded
                        decoded = base64.b64decode(clean_match)
                        print(f"🔍 Match {i+1} - Decoded length: {len(decoded)} bytes")
                        
                        # Check if it looks like a PNG (starts with PNG signature)
                        if decoded.startswith(b'\x89PNG\r\n\x1a\n'):
                            images.append({
                                'format': 'png',
                                'data': clean_match,
                                'source': 'agentcore_stdout'
                            })
                            print(f"✅ Match {i+1} - Valid PNG image extracted")
                        # Also check for JPEG signatures
                        elif decoded.startswith(b'\xff\xd8\xff'):
                            images.append({
                                'format': 'jpeg',
                                'data': clean_match,
                                'source': 'agentcore_stdout'
                            })
                            print(f"✅ Match {i+1} - Valid JPEG image extracted")
                        else:
                            print(f"⚠️  Match {i+1} - Invalid image signature")
                    else:
                        print(f"⚠️  Match {i+1} - Too short to be valid image")
                except Exception as e:
                    print(f"❌ Match {i+1} - Extraction error: {e}")
                    continue
        
        print(f"🎯 Final result: {len(images)} images extracted")
        return images
        
    except Exception as e:
        print(f"❌ Image extraction error: {e}")
        return []

def upload_files_to_agentcore_sandbox(files_data: list, aws_region: str) -> bool:
    """Upload files to AgentCore sandbox using writeFiles tool"""
    try:
        print(f"🔧 Uploading {len(files_data)} files to AgentCore sandbox...")
        
        with code_session(aws_region) as code_client:
            response = code_client.invoke("writeFiles", {"content": files_data})
            
            for event in response["stream"]:
                result = event.get("result", {})
                if result.get("isError", False):
                    error_content = result.get("content", [{}])
                    error_text = error_content[0].get("text", "Unknown error") if error_content else "Unknown error"
                    print(f"❌ File upload error: {error_text}")
                    return False
                else:
                    content = result.get("content", [])
                    for item in content:
                        if item.get("type") == "text":
                            print(f"✅ File upload result: {item.get('text', '')}")
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ File upload failed: {str(e)}")
        return False

def execute_chart_code_direct(code: str, session_files: list = None) -> tuple[str, list]:
    """Execute chart code directly with AgentCore to preserve full base64 output"""
    try:
        print(f"\n🎨 Direct AgentCore chart execution")
        print(f"📝 Code length: {len(code)} characters")
        
        # Clean the code to remove any markdown formatting
        clean_code = extract_python_code_from_prompt(code)
        print(f"🔧 Clean code length: {len(clean_code)} characters")
        
        with code_session(aws_region) as code_client:
            # Upload files to sandbox if provided
            if session_files:
                print(f"📁 Uploading {len(session_files)} files to sandbox...")
                files_data = []
                for file_info in session_files:
                    files_data.append({
                        "path": file_info['filename'],
                        "text": file_info['content']
                    })
                
                # Upload files using writeFiles tool
                upload_response = code_client.invoke("writeFiles", {"content": files_data})
                for event in upload_response["stream"]:
                    result = event.get("result", {})
                    if result.get("isError", False):
                        error_content = result.get("content", [{}])
                        error_text = error_content[0].get("text", "Unknown error") if error_content else "Unknown error"
                        print(f"❌ File upload error: {error_text}")
                        return f"File upload failed: {error_text}", []
                    else:
                        content = result.get("content", [])
                        for item in content:
                            if item.get("type") == "text":
                                print(f"✅ File upload: {item.get('text', '')}")
            
            # Execute the cleaned code
            response = code_client.invoke("executeCode", {
                "code": clean_code,
                "language": "python",
                "clearContext": False
            })
        
        # Process response directly without Strands-Agents truncation
        output_parts = []
        full_stdout = ""
        
        for event in response["stream"]:
            result = event.get("result", {})
            
            if result.get("isError", False):
                error_content = result.get("content", [{}])
                error_text = error_content[0].get("text", "Unknown error") if error_content else "Unknown error"
                print(f"❌ Direct execution error: {error_text}")
                return f"Error: {error_text}", []
            
            # Extract structured content
            structured_content = result.get("structuredContent", {})
            stdout = structured_content.get("stdout", "")
            stderr = structured_content.get("stderr", "")
            
            if stdout:
                output_parts.append(stdout)
                full_stdout += stdout
                print(f"📤 Direct stdout captured: {len(stdout)} characters")
            if stderr:
                output_parts.append(f"Errors: {stderr}")
                print(f"⚠️  Direct stderr: {stderr}")
        
        # Combine output
        final_output = "\n".join(output_parts) if output_parts else "Code executed successfully"
        
        # Extract images directly from full stdout
        images = extract_image_data(full_stdout)
        
        # Clean the output for display (remove image binary but keep analysis text)
        display_output = clean_output_for_display(final_output)
        
        print(f"✅ Direct execution completed:")
        print(f"   Output length: {len(final_output)}")
        print(f"   Display output length: {len(display_output)}")
        print(f"   Images extracted: {len(images)}")
        
        return display_output, images
        
    except Exception as e:
        print(f"❌ Direct AgentCore execution failed: {str(e)}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return f"Direct execution failed: {str(e)}", []

def detect_chart_code(code: str) -> bool:
    """Detect if code contains interactive elements like input() calls"""
    interactive_patterns = [
        'input(',
        'raw_input(',
        'sys.stdin.read',
        'getpass.getpass',
    ]
    
    code_lower = code.lower()
    return any(pattern in code_lower for pattern in interactive_patterns)

def prepare_interactive_code(code: str, inputs: List[str]) -> str:
    """Prepare code for execution with pre-provided inputs"""
    if not inputs:
        return code
    
    # Create a mock input function that uses pre-provided inputs
    input_setup = f"""
# Interactive input simulation
_provided_inputs = {inputs}
_input_index = 0

def input(prompt=''):
    global _input_index, _provided_inputs
    if prompt:
        print(prompt, end='')
    if _input_index < len(_provided_inputs):
        response = _provided_inputs[_input_index]
        _input_index += 1
        print(response)  # Echo the input
        return response
    else:
        print("No more inputs provided")
        return ""

# Override built-in input
__builtins__['input'] = input

"""
    
    return input_setup + "\n" + code

def extract_text_from_agent_result(agent_result) -> str:
    """Extract clean text content from Strands-Agents AgentResult object"""
    if not agent_result:
        return ""
    
    try:
        # Try to access the message attribute first
        if hasattr(agent_result, 'message'):
            message = agent_result.message
            print(f"🔍 AgentResult.message type: {type(message)}")
            
            # If message is a dict with content structure
            if isinstance(message, dict):
                if 'content' in message and isinstance(message['content'], list):
                    # Extract text from content array
                    text_parts = []
                    for item in message['content']:
                        if isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'])
                    if text_parts:
                        full_text = '\n'.join(text_parts)
                        print(f"✅ Extracted text from message.content array")
                        
                        # Extract actual execution output from AI commentary
                        actual_output = extract_execution_output_from_ai_response(full_text)
                        return actual_output
                
                # If message has direct text content
                if 'text' in message:
                    full_text = str(message['text'])
                    print(f"✅ Extracted text from message.text")
                    actual_output = extract_execution_output_from_ai_response(full_text)
                    return actual_output
            
            # If message is a string
            if isinstance(message, str):
                print(f"✅ Using message as string")
                actual_output = extract_execution_output_from_ai_response(message)
                return actual_output
        
        # Try other attributes
        if hasattr(agent_result, 'content'):
            content = agent_result.content
            if isinstance(content, str):
                print(f"✅ Using content attribute")
                actual_output = extract_execution_output_from_ai_response(content)
                return actual_output
        
        if hasattr(agent_result, 'text'):
            text = agent_result.text
            if isinstance(text, str):
                print(f"✅ Using text attribute")
                actual_output = extract_execution_output_from_ai_response(text)
                return actual_output
        
        # Fallback to string conversion
        result = str(agent_result)
        print(f"⚠️  Using str() fallback")
        actual_output = extract_execution_output_from_ai_response(result)
        return actual_output
        
    except Exception as e:
        print(f"❌ Error extracting text from AgentResult: {e}")
        return str(agent_result) if agent_result else ""

def extract_execution_output_from_ai_response(ai_response: str) -> str:
    """Extract the actual execution output from AI's commentary, prioritizing analysis text over raw output"""
    import re
    
    # For CSV analysis, prioritize AI analysis text over raw execution output
    if any(keyword in ai_response.lower() for keyword in ['dataset', 'dataframe', 'csv', 'analysis', 'statistics']):
        # Check if response contains IMAGE_DATA (indicating chart generation)
        if 'IMAGE_DATA:' in ai_response:
            # For chart generation, extract everything EXCEPT the image binary
            parts = ai_response.split('IMAGE_DATA:')
            if len(parts) > 1:
                # Take the part before IMAGE_DATA and any analysis after
                before_image = parts[0].strip()
                # Look for analysis text after the image data
                after_parts = parts[1].split('\n', 1)
                if len(after_parts) > 1:
                    after_image = after_parts[1].strip()
                    if after_image and not after_image.startswith(('iVBOR', '/9j/', 'data:')):
                        combined_analysis = f"{before_image}\n\n{after_image}".strip()
                        if combined_analysis:
                            print(f"🎯 Extracted analysis text (excluding image binary): {len(combined_analysis)} chars")
                            return combined_analysis
                
                # If no analysis after image, return the part before
                if before_image:
                    print(f"🎯 Extracted analysis text before image: {len(before_image)} chars")
                    return before_image
        
        # If it's data analysis without charts, prefer AI commentary over raw output
        if any(phrase in ai_response.lower() for phrase in [
            'analysis shows', 'data reveals', 'statistics indicate', 'summary:', 'insights:'
        ]):
            print(f"🎯 Using AI analysis commentary for data analysis: {len(ai_response)} chars")
            return ai_response
    
    # Pattern 1: Look for code blocks with output (for non-analysis cases)
    code_block_patterns = [
        r'```\s*\n(.*?)\n```',  # ``` ... ```
        r'```[a-zA-Z]*\s*\n(.*?)\n```',  # ```python ... ``` or similar
    ]
    
    for pattern in code_block_patterns:
        matches = re.findall(pattern, ai_response, re.DOTALL)
        if matches:
            output = matches[0].strip()
            # Skip if it's just image binary
            if not output.startswith(('iVBOR', '/9j/', 'IMAGE_DATA:')):
                print(f"🎯 Extracted output from code block: {len(output)} chars")
                return output
    
    # Pattern 2: Look for "output:" or "result:" sections
    output_patterns = [
        r'(?:output|result):\s*\n(.*?)(?:\n\n|\n[A-Z]|$)',
        r'(?:complete output|execution output):\s*\n(.*?)(?:\n\n|\n[A-Z]|$)',
    ]
    
    for pattern in output_patterns:
        matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
        if matches:
            output = matches[0].strip()
            if not output.startswith(('iVBOR', '/9j/', 'IMAGE_DATA:')):
                print(f"🎯 Extracted output from output section: {len(output)} chars")
                return output
    
    # Fallback: return the original response (but clean up image binary if present)
    if 'IMAGE_DATA:' in ai_response:
        cleaned = ai_response.split('IMAGE_DATA:')[0].strip()
        if cleaned:
            print(f"🎯 Cleaned response (removed image binary): {len(cleaned)} chars")
            return cleaned
    
    print(f"⚠️  Using original AI response as-is: {len(ai_response)} chars")
    return ai_response

def extract_python_code_from_prompt(input_text: str) -> str:
    """Extract clean Python code from markdown-formatted prompts or raw code"""
    import re
    
    # If the input contains markdown code blocks, extract the Python code
    if '```python' in input_text or '```' in input_text:
        # Pattern to match Python code blocks
        patterns = [
            r'```python\s*\n(.*?)\n```',  # ```python ... ```
            r'```\s*\n(.*?)\n```',       # ``` ... ```
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, input_text, re.DOTALL)
            if matches:
                # Return the first match (the actual Python code)
                clean_code = matches[0].strip()
                print(f"🔧 Extracted Python code from markdown block")
                return clean_code
    
    # If no markdown blocks found, check if it's a prompt with code
    if 'Execute this Python code' in input_text or 'python code' in input_text.lower():
        # Try to extract code after common prompt phrases
        lines = input_text.split('\n')
        code_lines = []
        in_code_section = False
        
        for line in lines:
            # Skip prompt text and markdown
            if any(phrase in line.lower() for phrase in [
                'execute this python code', 'python code', 'use the tool', 
                'return the complete output', '```'
            ]):
                continue
            
            # If line looks like Python code, include it
            if line.strip() and (
                line.startswith('import ') or 
                line.startswith('from ') or
                line.startswith('def ') or
                line.startswith('class ') or
                line.startswith('if ') or
                line.startswith('for ') or
                line.startswith('while ') or
                line.startswith('try:') or
                line.startswith('with ') or
                '=' in line or
                line.startswith('print(') or
                line.startswith('    ')  # Indented line
            ):
                in_code_section = True
                code_lines.append(line)
            elif in_code_section and line.strip() == '':
                code_lines.append(line)  # Keep empty lines within code
            elif in_code_section and not line.strip():
                continue
            elif in_code_section:
                # If we were in code section and hit non-code, we might be done
                break
        
        if code_lines:
            clean_code = '\n'.join(code_lines).strip()
            print(f"🔧 Extracted Python code from prompt text")
            return clean_code
    
    # If no special formatting detected, return as-is (assume it's already clean code)
    print(f"🔧 Using input as-is (no markdown formatting detected)")
    return input_text.strip()

@tool
def execute_python_code(code: str, description: str = "", files: list = None) -> str:
    """Execute Python code using AgentCore CodeInterpreter - reliable execution with proper output capture and file support"""
    
    # Extract clean Python code from markdown-formatted input
    clean_code = extract_python_code_from_prompt(code)
    
    if description:
        clean_code = f"# {description}\n{clean_code}"
    
    print(f"\n🔧 Original input length: {len(code)}")
    print(f"🔧 Clean code length: {len(clean_code)}")
    print(f"🔧 Files provided: {len(files) if files else 0}")
    print(f"🔧 Clean code preview: {clean_code[:200]}...")
    
    try:
        with code_session(aws_region) as code_client:
            # Upload files to sandbox if provided
            if files:
                print(f"📁 Uploading {len(files)} files to sandbox...")
                files_data = []
                for file_info in files:
                    files_data.append({
                        "path": file_info.get('filename', 'uploaded_file.csv'),
                        "text": file_info.get('content', '')
                    })
                
                # Upload files using writeFiles tool
                upload_response = code_client.invoke("writeFiles", {"content": files_data})
                for event in upload_response["stream"]:
                    result = event.get("result", {})
                    if result.get("isError", False):
                        error_content = result.get("content", [{}])
                        error_text = error_content[0].get("text", "Unknown error") if error_content else "Unknown error"
                        print(f"❌ File upload error: {error_text}")
                        return f"File upload failed: {error_text}"
                    else:
                        content = result.get("content", [])
                        for item in content:
                            if item.get("type") == "text":
                                print(f"✅ File upload: {item.get('text', '')}")
            
            # Execute the code
            response = code_client.invoke("executeCode", {
                "code": clean_code,
                "language": "python",
                "clearContext": False
            })
        
        # Process the response stream to capture all output
        output_parts = []
        
        for event in response["stream"]:
            result = event.get("result", {})
            
            if result.get("isError", False):
                error_content = result.get("content", [{}])
                error_text = error_content[0].get("text", "Unknown error") if error_content else "Unknown error"
                print(f"❌ AgentCore execution error: {error_text}")
                return f"Error: {error_text}"
            
            # Extract structured content (stdout, stderr)
            structured_content = result.get("structuredContent", {})
            stdout = structured_content.get("stdout", "")
            stderr = structured_content.get("stderr", "")
            
            if stdout:
                output_parts.append(stdout)
                print(f"📤 Stdout captured: {len(stdout)} characters")
            if stderr:
                output_parts.append(f"Errors: {stderr}")
                print(f"⚠️  Stderr captured: {len(stderr)} characters")
        
        # Combine all output
        final_output = "\n".join(output_parts) if output_parts else "Code executed successfully (no output)"
        
        print(f"✅ AgentCore execution completed - Output length: {len(final_output)}")
        return final_output
                
    except Exception as e:
        print(f"❌ AgentCore execution error: {str(e)}")
        import traceback
        print(f"📋 Full traceback: {traceback.format_exc()}")
        return f"Execution failed: {str(e)}"

@lru_cache(maxsize=1)
def get_extended_botocore_config():
    """Get BotocoreConfig with extended timeouts for long-running code execution
    
    This configuration is essential for complex code execution that may take several minutes.
    Based on Strands Agents documentation: https://strandsagents.com/1.0.x/documentation/docs/user-guide/concepts/model-providers/amazon-bedrock/
    """
    # Get timeout values from environment variables with sensible defaults
    read_timeout = int(os.getenv('AWS_READ_TIMEOUT', '600'))  # 10 minutes default
    connect_timeout = int(os.getenv('AWS_CONNECT_TIMEOUT', '120'))  # 2 minutes default
    max_retries = int(os.getenv('AWS_MAX_RETRIES', '5'))  # 5 retries default
    
    return Config(
        read_timeout=read_timeout,
        connect_timeout=connect_timeout,
        retries={
            'max_attempts': max_retries,
            'mode': 'adaptive'
        },
        max_pool_connections=50
    )

@lru_cache(maxsize=3)
def create_bedrock_model_with_fallback(aws_region: str):
    """Create BedrockModel with Claude Sonnet 3.7 primary and Nova Premier fallback using inference profiles - cached"""
    
    cache_key = f"model_{aws_region}"
    if cache_key in _model_cache:
        print(f"✅ Using cached model for region {aws_region}")
        return _model_cache[cache_key]
    
    # Primary model: Claude Sonnet 3.7 (Inference Profile)
    primary_model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    fallback_model_id = "us.amazon.nova-premier-v1:0"
    default_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    
    print(f"🤖 Attempting to use primary inference profile: {primary_model_id}")
    
    # Try primary model (inference profile)
    try:
        primary_model = BedrockModel(
            model_id=primary_model_id,
            aws_region=aws_region,
            botocore_config=get_extended_botocore_config()
        )
        print(f"✅ Primary inference profile {primary_model_id} initialized successfully")
        result = (primary_model, primary_model_id)
        _model_cache[cache_key] = result
        return result
    except Exception as e:
        print(f"⚠️  Primary inference profile failed: {e}")
        print(f"🔄 Trying fallback inference profile: {fallback_model_id}")
        
        # Try fallback model (inference profile)
        try:
            fallback_model = BedrockModel(
                model_id=fallback_model_id,
                aws_region=aws_region,
                botocore_config=get_extended_botocore_config()
            )
            print(f"✅ Fallback inference profile {fallback_model_id} initialized successfully")
            result = (fallback_model, fallback_model_id)
            _model_cache[cache_key] = result
            return result
        except Exception as fallback_error:
            print(f"⚠️  Fallback inference profile failed: {fallback_error}")
            print(f"🔄 Using default model as last resort: {default_model_id}")
            
            # Last resort: standard model (not inference profile)
            try:
                default_model = BedrockModel(
                    model_id=default_model_id,
                    aws_region=aws_region,
                    botocore_config=get_extended_botocore_config()
                )
                print(f"✅ Default model {default_model_id} initialized")
                result = (default_model, default_model_id)
                _model_cache[cache_key] = result
                return result
            except Exception as final_error:
                raise Exception(f"All model initialization attempts failed: {final_error}")

def setup_aws_credentials():
    """Setup AWS credentials - uses cached version"""
    global _aws_session_cache
    if _aws_session_cache:
        print("✅ Using cached AWS session")
        return _aws_session_cache
    
    result = get_aws_credentials()
    _aws_session_cache = result
    return result

def initialize_agents():
    """Initialize agents using strands-agents with AgentCore CodeInterpreter tool - cached"""
    global code_generator_agent, code_executor_agent, executor_type, current_model_id
    
    # Check cache first
    if 'code_generator_agent' in _agents_cache and 'code_executor_agent' in _agents_cache:
        print("✅ Using cached agents")
        code_generator_agent = _agents_cache['code_generator_agent']
        code_executor_agent = _agents_cache['code_executor_agent']
        current_model_id = _agents_cache['current_model_id']
        executor_type = _agents_cache['executor_type']
        return
    
    if not aws_session:
        raise Exception("AWS session not available. Check AWS credentials.")
    
    try:
        print("🤖 Initializing agents...")
        
        # Initialize Bedrock model with fallback logic
        bedrock_model, model_id = create_bedrock_model_with_fallback(aws_region)
        print(f"🎯 Using model: {model_id}")
        
        # Initialize Code Generator Agent using strands-agents
        code_generator_agent = Agent(
            model=bedrock_model,
            system_prompt=f"""You are a Python code generator specialist powered by {model_id}. Your role is to:
            1. Generate clean, well-commented Python code based on user requirements
            2. Follow Python best practices and PEP 8 style guidelines
            3. Include appropriate error handling where needed
            4. Only return executable Python code without explanations or markdown formatting
            5. Make sure the code is complete and runnable
            6. Do not include any text before or after the code
            
            Focus on creating practical, efficient code that solves the user's specific problem.
            Return ONLY the Python code, no explanations, no markdown, no additional text."""
        )
        
        # Test AgentCore availability
        with code_session(aws_region) as test_client:
            test_response = test_client.invoke("executeCode", {
                "code": "print('AgentCore initialization test successful')",
                "language": "python",
                "clearContext": True
            })
        
        # AgentCore is working - create executor agent with AgentCore tool
        executor_type = "agentcore"
        
        # Create Code Executor Agent with AgentCore tool - following the sample system prompt
        SYSTEM_PROMPT = f"""You are a helpful AI assistant powered by {model_id} that validates all answers through code execution.

VALIDATION PRINCIPLES:
1. When making claims about code, algorithms, or calculations - write code to verify them
2. Use execute_python_code to test mathematical calculations, algorithms, and logic
3. Create test scripts to validate your understanding before giving answers
4. Always show your work with actual code execution
5. If uncertain, explicitly state limitations and validate what you can

APPROACH:
- If asked about a programming concept, implement it in code to demonstrate
- If asked for calculations, compute them programmatically AND show the code
- If implementing algorithms, include test cases to prove correctness
- Document your validation process for transparency
- The sandbox maintains state between executions, so you can refer to previous results

TOOL AVAILABLE:
- execute_python_code: Run Python code and see output

RESPONSE FORMAT: The execute_python_code tool returns execution results including stdout, stderr, and any errors."""
        
        code_executor_agent = Agent(
            model=bedrock_model,
            tools=[execute_python_code],
            system_prompt=SYSTEM_PROMPT
        )
        
        print("✅ Agents initialized successfully:")
        print(f"   - Code Generator: Strands-Agents Agent with {model_id}")
        print(f"   - Code Executor: Strands-Agents Agent with {model_id} + AgentCore CodeInterpreter")
        
        # Cache the agents
        current_model_id = model_id
        _agents_cache['code_generator_agent'] = code_generator_agent
        _agents_cache['code_executor_agent'] = code_executor_agent
        _agents_cache['current_model_id'] = current_model_id
        _agents_cache['executor_type'] = executor_type
        
    except Exception as e:
        print(f"❌ Error initializing agents: {str(e)}")
        print("   Make sure you have bedrock-agentcore permissions")
        raise e

# Startup is now handled by lifespan context manager

def get_or_create_session(session_id: Optional[str] = None) -> CodeInterpreterSession:
    """Get existing session or create new one"""
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    if session_id not in active_sessions:
        active_sessions[session_id] = CodeInterpreterSession(session_id)
    
    return active_sessions[session_id]

# Utility functions for code analysis
def detect_chart_code(code: str) -> bool:
    """Detect if code contains chart/visualization generation"""
    chart_indicators = [
        'plt.', 'matplotlib', 'seaborn', 'plotly', 'sns.',
        'plt.show()', 'plt.savefig(', 'fig.show()', 
        'IMAGE_DATA:', 'base64.b64encode', 'io.BytesIO'
    ]
    code_lower = code.lower()
    return any(indicator.lower() in code_lower for indicator in chart_indicators)

def detect_interactive_code(code: str) -> bool:
    """Detect if code requires interactive input"""
    interactive_patterns = [
        'input(', 'raw_input(', 'getpass.getpass(',
        'sys.stdin.read', 'input =', 'user_input'
    ]
    code_lower = code.lower()
    return any(pattern.lower() in code_lower for pattern in interactive_patterns)

def prepare_interactive_code(code: str, inputs: list) -> str:
    """Prepare interactive code with pre-provided inputs - OPTIMIZED for faster execution"""
    if not inputs:
        return code
    
    # OPTIMIZATION: More efficient input replacement
    input_setup = f"""# Pre-provided inputs (optimized)
_inputs = {inputs}
_input_index = 0

def input(prompt=''):
    global _input_index
    if _input_index < len(_inputs):
        value = _inputs[_input_index]
        _input_index += 1
        print(prompt + str(value))
        return value
    return ''

"""
    
    return input_setup + code

@app.post("/api/generate-code")
async def generate_code(request: CodeGenerationRequest):
    """Generate Python code using the strands-agents code generator agent"""
    try:
        session = get_or_create_session(request.session_id)
        
        # Check if prompt mentions files but no CSV is uploaded
        file_keywords = ['file', 'csv', 'data', 'dataset', 'load', 'read', 'import', 'upload']
        mentions_file = any(keyword in request.prompt.lower() for keyword in file_keywords)
        
        if mentions_file and not session.uploaded_csv:
            return {
                "success": False,
                "requires_file": True,
                "message": "Your request mentions working with files. Please upload a CSV file first.",
                "session_id": session.session_id
            }
        
        # Prepare prompt with CSV context if available
        enhanced_prompt = request.prompt
        
        # Check if the request involves visualization/charts
        chart_keywords = ['plot', 'chart', 'graph', 'visualiz', 'histogram', 'scatter', 'bar chart', 'line chart', 'pie chart', 'heatmap', 'matplotlib', 'seaborn', 'plotly']
        needs_visualization = any(keyword in request.prompt.lower() for keyword in chart_keywords)
        
        if session.uploaded_csv:
            csv_info = f"""
You have access to a CSV file named '{session.uploaded_csv['filename']}' with the following content preview:

```csv
{session.uploaded_csv['content'][:1000]}{'...' if len(session.uploaded_csv['content']) > 1000 else ''}
```

When generating code, assume this CSV data is available and can be loaded using pandas.read_csv() or similar methods. 
Use the filename '{session.uploaded_csv['filename']}' in your code.

User request: {request.prompt}
"""
            enhanced_prompt = csv_info
        
        # Add chart rendering instructions if visualization is needed
        if needs_visualization:
            chart_instructions = """

IMPORTANT: For reliable chart rendering in the web interface, use this approach:

```python
import matplotlib.pyplot as plt
import numpy as np
import base64
import io

# Create your plot
x = np.linspace(0, 10, 100)
y = np.sin(x)
plt.figure(figsize=(10, 6))
plt.plot(x, y)
plt.title('Sine Wave')
plt.xlabel('X')
plt.ylabel('Y')
plt.grid(True)

# Save and capture the plot for web display
buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
plt.close()  # Close to free memory

# Output the image data for web interface
print(f"IMAGE_DATA:{image_base64}")
print("Chart generated successfully!")
```

This ensures your charts are properly displayed in the web interface.
"""
            enhanced_prompt += chart_instructions
        
        # Use the strands-agents agent for code generation
        agent_result = code_generator_agent(enhanced_prompt)
        
        # Extract string content from AgentResult
        generated_code = str(agent_result) if agent_result is not None else ""
        
        # Store generation in session history
        session.conversation_history.append({
            "type": "generation",
            "prompt": request.prompt,
            "enhanced_prompt": enhanced_prompt if session.uploaded_csv else None,
            "generated_code": generated_code,
            "agent": "strands_code_generator",
            "csv_used": session.uploaded_csv['filename'] if session.uploaded_csv else None,
            "timestamp": time.time()
        })
        
        return {
            "success": True,
            "code": generated_code,
            "session_id": session.session_id,
            "agent_used": "strands_code_generator",
            "csv_file_used": session.uploaded_csv['filename'] if session.uploaded_csv else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")

@app.post("/api/analyze-code")
async def analyze_code(request: CodeExecutionRequest):
    """Analyze code to detect interactive elements and suggest inputs - OPTIMIZED"""
    try:
        is_interactive = detect_interactive_code(request.code)
        
        if is_interactive:
            # OPTIMIZATION: Faster, more focused analysis
            analysis_prompt = f"""Analyze this Python code and identify the input() calls. Be concise:

```python
{request.code}
```

Provide:
1. Number of input() calls
2. What each input should be (name, age, etc.)
3. Example values for testing

Keep response short and practical."""
            
            analysis_result = code_generator_agent(analysis_prompt)
            
            return {
                "success": True,
                "interactive": True,
                "analysis": analysis_result,
                "suggestions": "Provide inputs in the order they appear in the code"
            }
        else:
            return {
                "success": True,
                "interactive": False,
                "analysis": "This code does not require interactive input.",
                "suggestions": None
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code analysis failed: {str(e)}")

@app.post("/api/execute-code")
async def execute_code(request: CodeExecutionRequest):
    """Execute Python code using hybrid approach: direct AgentCore for charts, Strands-Agents for others"""
    try:
        session = get_or_create_session(request.session_id)
        
        # Track execution start time
        execution_start_time = time.time()
        
        # Check if code is interactive
        is_interactive = request.interactive or detect_interactive_code(request.code)
        
        # Try to find the original prompt from recent conversation history
        user_prompt = None
        if session.conversation_history:
            # Look for the most recent generation entry with a prompt
            for entry in reversed(session.conversation_history):
                if entry.get('prompt'):  # Direct prompt field
                    user_prompt = entry['prompt']
                    break
                elif entry.get('type') == 'generation' and entry.get('generated_code'):
                    # Check if this generated code matches the current code being executed
                    if entry.get('generated_code') and request.code.strip() in entry.get('generated_code', ''):
                        user_prompt = entry.get('prompt')
                        break
        
        # If no prompt found, check if this is a direct code execution
        if not user_prompt:
            # For direct executions, we can create a descriptive prompt based on the code
            code_lines = request.code.strip().split('\n')
            if len(code_lines) == 1 and len(code_lines[0]) < 100:
                user_prompt = f"Execute: {code_lines[0]}"
            elif 'input(' in request.code:
                user_prompt = "Interactive code execution"
            elif any(keyword in request.code.lower() for keyword in ['import matplotlib', 'plt.', 'plot', 'chart']):
                user_prompt = "Generate visualization/chart"
            elif 'import pandas' in request.code or 'pd.' in request.code:
                user_prompt = "Data analysis with pandas"
            else:
                user_prompt = "Direct code execution"
        
        # Prepare code for execution
        if is_interactive and request.inputs:
            prepared_code = prepare_interactive_code(request.code, request.inputs)
            print(f"🔄 Interactive code prepared with {len(request.inputs)} inputs")
        else:
            prepared_code = request.code
        
        # Check if this is chart/visualization code
        is_chart_code = detect_chart_code(prepared_code)
        
        # Get session files for sandbox upload
        session_files = []
        if session.uploaded_csv:
            session_files.append({
                'filename': session.uploaded_csv['filename'],
                'content': session.uploaded_csv['content']
            })
        
        # REVERTED: Use original logic - only force direct AgentCore for charts and files, NOT for interactive
        if is_chart_code or session_files:
            print(f"🎨 Chart code detected - using direct AgentCore execution")
            
            # Use direct AgentCore execution to preserve full base64 output
            execution_result_str, images = execute_chart_code_direct(prepared_code, session_files)
            agent_used = "direct_agentcore_charts"
            
        else:
            print(f"📝 Regular code - using Strands-Agents execution")
            
            # For regular code, if files are needed, use direct AgentCore as well
            # since Strands-Agents tools can't easily access session files
            if session_files:
                print(f"📁 Files detected - switching to direct AgentCore for file access")
                execution_result_str, images = execute_chart_code_direct(prepared_code, session_files)
                agent_used = "direct_agentcore_with_files"
            else:
                # Use strands-agents with AgentCore tool for regular code without files
                execution_prompt = f"""Execute this Python code using the execute_python_code tool:

```python
{prepared_code}
```

Use the tool to run the code and return the complete output."""
                
                execution_result = code_executor_agent(execution_prompt)
                
                # Debug the AgentResult structure
                print(f"🔍 AgentResult type: {type(execution_result)}")
                
                # Extract the actual text content from AgentResult
                execution_result_str = extract_text_from_agent_result(execution_result)
                print(f"📊 Extracted text length: {len(execution_result_str)}")
                
                # Extract image data from execution results
                images = extract_image_data(execution_result_str)
                agent_used = "strands_agents_with_agentcore"
        
        # Calculate execution duration
        execution_end_time = time.time()
        execution_duration = execution_end_time - execution_start_time
        
        # Store execution in session history
        session.code_history.append(request.code)
        session.execution_results.append({
            "code": request.code,
            "result": execution_result_str,
            "agent": agent_used,
            "executor_type": "agentcore",
            "interactive": is_interactive,
            "inputs_provided": request.inputs if is_interactive else None,
            "images": images,
            "is_chart_code": is_chart_code,
            "timestamp": execution_end_time,
            "execution_duration": execution_duration,
            "prompt": user_prompt,
            "start_time": execution_start_time,
            "end_time": execution_end_time
        })
        
        return {
            "success": True,
            "result": execution_result_str,
            "session_id": session.session_id,
            "agent_used": agent_used,
            "executor_type": "agentcore",
            "interactive": is_interactive,
            "inputs_used": request.inputs if is_interactive else None,
            "images": images,
            "is_chart_code": is_chart_code
        }
        
    except Exception as e:
        print(f"❌ Code execution failed: {str(e)}")
        import traceback
        print(f"📋 Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Code execution failed: {str(e)}")

@app.post("/api/sessions/{session_id}/clear-csv")
async def clear_csv_from_session(session_id: str):
    """Clear CSV file from session and AgentCore context"""
    try:
        session = get_or_create_session(session_id)
        
        if session.uploaded_csv:
            filename = session.uploaded_csv['filename']
            
            # Clear CSV from session
            session.uploaded_csv = None
            
            # Add to conversation history
            session.conversation_history.append({
                "type": "csv_removal",
                "filename": filename,
                "timestamp": time.time()
            })
            
            print(f"🗑️ CSV file '{filename}' cleared from session {session_id}")
            
            return {
                "success": True,
                "message": f"CSV file '{filename}' removed successfully",
                "session_id": session_id
            }
        else:
            return {
                "success": True,
                "message": "No CSV file to remove",
                "session_id": session_id
            }
            
    except Exception as e:
        print(f"❌ Error clearing CSV from session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear CSV: {str(e)}")

@app.post("/api/upload-csv")
async def upload_csv_file(request: FileUploadRequest):
    """Upload and process a CSV file"""
    try:
        session = get_or_create_session(request.session_id)
        
        # Validate CSV content
        if not request.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Store CSV file in session
        session.conversation_history.append({
            "type": "csv_upload",
            "filename": request.filename,
            "content": request.content,
            "timestamp": time.time()
        })
        
        # Store CSV data for code generation
        session.uploaded_csv = {
            "filename": request.filename,
            "content": request.content,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        return {
            "success": True,
            "message": f"CSV file {request.filename} uploaded successfully",
            "session_id": session.session_id,
            "filename": request.filename,
            "preview": request.content[:500] + "..." if len(request.content) > 500 else request.content
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV upload failed: {str(e)}")

@app.post("/api/upload-file")
async def upload_file(request: FileUploadRequest):
    """Upload and process a Python file"""
    try:
        session = get_or_create_session(request.session_id)
        
        # Store file in session
        session.conversation_history.append({
            "type": "file_upload",
            "filename": request.filename,
            "content": request.content,
            "timestamp": time.time()
        })
        
        return {
            "success": True,
            "message": f"File {request.filename} uploaded successfully",
            "session_id": session.session_id,
            "content": request.content
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.get("/api/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get session history"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = active_sessions[session_id]
        
        return {
            "success": True,
            "session_id": session_id,
            "conversation_history": session.conversation_history,
            "execution_results": session.execution_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}")

@app.get("/api/agents/status")
async def get_agents_status():
    """Get status of all agents"""
    try:
        current_model = globals().get('current_model_id', 'Unknown')
        
        agents_info = [
            {
                "name": "code_generator",
                "framework": "strands-agents",
                "model": current_model,
                "purpose": "Generate Python code from natural language",
                "status": "active" if code_generator_agent else "inactive"
            },
            {
                "name": "code_executor", 
                "framework": executor_type,
                "model": current_model,
                "purpose": "Execute Python code safely" if executor_type == "agentcore" else "Simulate Python code execution",
                "status": "active" if 'code_executor_agent' in globals() else "inactive",
                "type": "AgentCore CodeInterpreter" if executor_type == "agentcore" else "Strands Simulation"
            }
        ]
        
        architecture = f"Hybrid: Strands-Agents + AgentCore ({current_model})" if executor_type == "agentcore" else f"Strands-Agents Framework ({current_model})"
        
        return {
            "agents": agents_info,
            "total": len(agents_info),
            "architecture": architecture,
            "executor_type": executor_type,
            "current_model": current_model,
            "aws_region": aws_region,
            "authentication": "AWS Profile" if os.getenv('AWS_PROFILE') else "Access Keys"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agents status: {str(e)}")

# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    print(f"WebSocket connected for session {session_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "generate_code":
                # Handle code generation via WebSocket
                try:
                    agent_result = code_generator_agent(message["prompt"])
                    
                    # Extract string content from AgentResult
                    generated_code = str(agent_result) if agent_result is not None else ""
                    
                    await websocket.send_text(json.dumps({
                        "type": "code_generated",
                        "success": True,
                        "code": generated_code,
                        "session_id": session_id
                    }))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "success": False,
                        "error": str(e)
                    }))
            
            elif message["type"] == "execute_code":
                # Handle code execution via WebSocket
                try:
                    if executor_type == "agentcore":
                        execution_result = code_executor_agent(f"Execute this code: {message['code']}")
                    else:
                        execution_result = code_executor_agent(f"Simulate execution of: {message['code']}")
                    
                    await websocket.send_text(json.dumps({
                        "type": "execution_result",
                        "success": True,
                        "result": execution_result,
                        "session_id": session_id
                    }))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "success": False,
                        "error": str(e)
                    }))
                    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    current_model = globals().get('current_model_id', 'Unknown')
    
    return {
        "status": "healthy", 
        "code_generator_ready": code_generator_agent is not None,
        "code_executor_ready": 'code_executor_agent' in globals(),
        "executor_type": executor_type,
        "current_model": current_model,
        "aws_region": aws_region,
        "authentication": "AWS Profile" if os.getenv('AWS_PROFILE') else "Access Keys",
        "architecture": {
            "code_generation": f"Strands-Agents Agent ({current_model})",
            "code_execution": f"{executor_type.title().replace('_', ' ')} Agent ({current_model})"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
