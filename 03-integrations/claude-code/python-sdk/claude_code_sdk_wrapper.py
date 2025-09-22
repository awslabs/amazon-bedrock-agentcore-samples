"""
Claude Code SDK Wrapper for Python

Provides a programmatic interface to Claude Code functionality,
making it easy to integrate Claude Code into Python applications.
"""

import os
import json
import subprocess
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Output format options for Claude Code"""
    JSON = "json"
    TEXT = "text"
    STREAM_JSON = "stream-json"


class PermissionMode(Enum):
    """Permission handling modes"""
    ACCEPT_EDITS = "acceptEdits"
    ASK_USER = "askUser"


@dataclass
class ClaudeCodeConfig:
    """Configuration for Claude Code SDK"""
    timeout: int = 600  # Default 10 minutes
    verbose: bool = False
    default_tools: str = "Bash,Read,Write,Replace,Search,List,WebFetch"
    output_format: OutputFormat = OutputFormat.JSON
    permission_mode: PermissionMode = PermissionMode.ACCEPT_EDITS
    claude_executable: str = "claude"  # Path to claude CLI


@dataclass
class ExecutionResult:
    """Result from Claude Code execution"""
    success: bool
    result: str
    session_id: Optional[str] = None
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    num_turns: Optional[int] = None
    error: Optional[str] = None
    raw_output: Optional[Dict[str, Any]] = None


class ClaudeCodeSession:
    """Manages a conversation session with Claude Code"""
    
    def __init__(self, session_id: str, config: ClaudeCodeConfig):
        self.session_id = session_id
        self.config = config
        self.history: List[Dict[str, Any]] = []
    
    def send(self, prompt: str, **kwargs) -> ExecutionResult:
        """Send a message in this session"""
        agent = ClaudeCodeAgent(self.config)
        result = agent.execute(
            prompt=prompt,
            session_id=self.session_id,
            **kwargs
        )
        self.history.append({
            "prompt": prompt,
            "result": result.result,
            "success": result.success
        })
        return result
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.history


class ClaudeCodeAgent:
    """Main SDK class for interacting with Claude Code"""
    
    def __init__(self, config: Optional[ClaudeCodeConfig] = None):
        """
        Initialize Claude Code Agent
        
        Args:
            config: Configuration object (uses defaults if not provided)
        """
        self.config = config or ClaudeCodeConfig()
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify Claude Code CLI is installed and accessible"""
        try:
            result = subprocess.run(
                [self.config.claude_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError(f"Claude Code CLI not working properly: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Claude Code CLI not found at '{self.config.claude_executable}'. "
                "Please install it or specify the correct path in config.claude_executable"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to verify Claude Code installation: {e}")
    
    def execute(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        continue_conversation: bool = False,
        allowed_tools: Optional[str] = None,
        append_system_prompt: Optional[str] = None,
        output_format: Optional[OutputFormat] = None,
        permission_mode: Optional[PermissionMode] = None,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute a prompt with Claude Code
        
        Args:
            prompt: The task to execute
            session_id: Optional session ID to resume
            continue_conversation: Continue most recent conversation
            allowed_tools: Comma-separated list of allowed tools
            append_system_prompt: Additional system instructions
            output_format: Output format override
            permission_mode: Permission mode override
            timeout: Execution timeout override
            
        Returns:
            ExecutionResult with the outcome
        """
        # Build command
        cmd = [self.config.claude_executable, "-p", prompt]
        
        # Use provided values or fall back to config
        output_fmt = output_format or self.config.output_format
        perm_mode = permission_mode or self.config.permission_mode
        exec_timeout = timeout or self.config.timeout
        tools = allowed_tools or self.config.default_tools
        
        # Add parameters
        cmd.extend(["--output-format", output_fmt.value])
        cmd.extend(["--permission-mode", perm_mode.value])
        
        if tools:
            cmd.extend(["--allowedTools", tools])
        
        if append_system_prompt:
            cmd.extend(["--append-system-prompt", append_system_prompt])
        
        if session_id:
            cmd.extend(["--resume", session_id])
        elif continue_conversation:
            cmd.append("--continue")
        
        if self.config.verbose:
            cmd.append("--verbose")
        
        # Execute
        logger.info(f"Executing Claude Code: {prompt[:50]}...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=exec_timeout
            )
            
            # Parse result based on format
            if output_fmt == OutputFormat.JSON:
                return self._parse_json_output(result.stdout, result.stderr)
            else:
                return self._parse_text_output(result.stdout, result.stderr, result.returncode)
                
        except subprocess.TimeoutExpired:
            logger.error(f"Execution timed out after {exec_timeout} seconds")
            return ExecutionResult(
                success=False,
                result="",
                error=f"Execution timed out after {exec_timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                result="",
                error=str(e)
            )
    
    def _parse_json_output(self, stdout: str, stderr: str) -> ExecutionResult:
        """Parse JSON formatted output"""
        try:
            data = json.loads(stdout)
            return ExecutionResult(
                success=not data.get("is_error", False),
                result=data.get("result", ""),
                session_id=data.get("session_id"),
                cost_usd=data.get("total_cost_usd"),
                duration_ms=data.get("duration_ms"),
                num_turns=data.get("num_turns"),
                error=data.get("error"),
                raw_output=data
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return ExecutionResult(
                success=False,
                result=stdout,
                error=f"JSON parse error: {str(e)}\nStderr: {stderr}"
            )
    
    def _parse_text_output(self, stdout: str, stderr: str, returncode: int) -> ExecutionResult:
        """Parse text formatted output"""
        return ExecutionResult(
            success=returncode == 0,
            result=stdout,
            error=stderr if stderr else None
        )
    
    def create_session(self, initial_prompt: Optional[str] = None) -> ClaudeCodeSession:
        """
        Create a new conversation session
        
        Args:
            initial_prompt: Optional initial prompt to start the session
            
        Returns:
            ClaudeCodeSession object for continued conversation
        """
        if initial_prompt:
            result = self.execute(initial_prompt)
            if result.session_id:
                session = ClaudeCodeSession(result.session_id, self.config)
                session.history.append({
                    "prompt": initial_prompt,
                    "result": result.result,
                    "success": result.success
                })
                return session
            else:
                raise RuntimeError("Failed to get session ID from initial prompt")
        else:
            # Create empty session - ID will be set on first message
            import uuid
            session_id = str(uuid.uuid4())
            return ClaudeCodeSession(session_id, self.config)
    
    def execute_batch(
        self,
        prompts: List[str],
        sequential: bool = True,
        **kwargs
    ) -> List[ExecutionResult]:
        """
        Execute multiple prompts
        
        Args:
            prompts: List of prompts to execute
            sequential: If True, execute in sequence with session continuation
            **kwargs: Additional parameters passed to execute()
            
        Returns:
            List of ExecutionResults
        """
        results = []
        session_id = None
        
        for i, prompt in enumerate(prompts):
            if sequential and i > 0:
                # Continue conversation from previous prompt
                result = self.execute(
                    prompt=prompt,
                    session_id=session_id,
                    **kwargs
                )
            else:
                result = self.execute(prompt=prompt, **kwargs)
            
            results.append(result)
            
            if sequential and result.session_id:
                session_id = result.session_id
        
        return results
    
    def validate_tools(self, tools: str) -> bool:
        """
        Validate tool names
        
        Args:
            tools: Comma-separated list of tools
            
        Returns:
            True if all tools are valid
        """
        valid_tools = {
            "Bash", "Read", "Write", "Replace", "Search",
            "List", "WebFetch", "AskFollowup", "Browser",
            "MCPTool", "MCPResource"
        }
        
        tool_list = [t.strip() for t in tools.split(",")]
        invalid = [t for t in tool_list if t not in valid_tools]
        
        if invalid:
            logger.warning(f"Invalid tools: {invalid}")
            return False
        return True


# Convenience functions
def quick_execute(prompt: str, **kwargs) -> str:
    """
    Quick execution with default settings
    
    Args:
        prompt: The task to execute
        **kwargs: Additional parameters
        
    Returns:
        Result string or error message
    """
    agent = ClaudeCodeAgent()
    result = agent.execute(prompt, **kwargs)
    return result.result if result.success else f"Error: {result.error}"


def create_aws_deployment_agent() -> ClaudeCodeAgent:
    """
    Create an agent pre-configured for AWS deployments
    
    Returns:
        ClaudeCodeAgent configured for AWS operations
    """
    config = ClaudeCodeConfig(
        timeout=1200,  # 20 minutes for deployments
        default_tools="Bash,Read,Write,Replace,Search,List,WebFetch",
        permission_mode=PermissionMode.ACCEPT_EDITS
    )
    return ClaudeCodeAgent(config)


def create_code_review_agent() -> ClaudeCodeAgent:
    """
    Create an agent pre-configured for code review
    
    Returns:
        ClaudeCodeAgent configured for code review
    """
    config = ClaudeCodeConfig(
        default_tools="Read,List,Search",  # Read-only tools
        permission_mode=PermissionMode.ASK_USER
    )
    return ClaudeCodeAgent(config)


if __name__ == "__main__":
    # Example usage
    print("Claude Code SDK Wrapper")
    print("-" * 50)
    
    # Create agent
    agent = ClaudeCodeAgent()
    
    # Simple execution
    result = agent.execute("Create a simple hello world Python script")
    
    if result.success:
        print(f"Success! Result: {result.result[:200]}...")
        if result.cost_usd:
            print(f"Cost: ${result.cost_usd:.4f}")
    else:
        print(f"Failed: {result.error}")
