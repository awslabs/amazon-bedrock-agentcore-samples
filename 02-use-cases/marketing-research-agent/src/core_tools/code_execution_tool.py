import logging
import sys
import io
import traceback
from typing import Dict, Any, Optional
from contextlib import redirect_stdout, redirect_stderr
from strands.tools import tool

logger = logging.getLogger(__name__)


class CodeExecutionError(Exception):
    """Custom exception for code execution errors."""
    pass


@tool
def python_code_execution_tool(
    code: str,
    timeout_seconds: int = 30
) -> Dict[str, Any]:
    """
    Execute Python code that solves business questions and produces actionable results.
    
    Args:
        code: Python code to execute that should produce business insights
        timeout_seconds: Maximum execution time (default: 30 seconds)
    
    Returns:
        Dictionary containing business results and insights
    """
    try:
        logger.info("Executing Python code for data analysis")
        
        # Prepare execution environment with safe imports
        execution_globals = {
            '__builtins__': {
                'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
                'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
                'range': range, 'enumerate': enumerate, 'zip': zip, 'map': map,
                'filter': filter, 'sum': sum, 'min': min, 'max': max, 'abs': abs,
                'round': round, 'sorted': sorted, 'reversed': reversed, 'print': print,
                'type': type, 'isinstance': isinstance,
            }
        }
        
        # Add safe data analysis libraries
        safe_imports = {
            'pandas': 'pd',
            'numpy': 'np',
            'json': 'json',
            'math': 'math',
            'statistics': 'statistics',
            'datetime': 'datetime',
        }
        
        # Import libraries
        for module, alias in safe_imports.items():
            try:
                imported_module = __import__(module)
                execution_globals[alias] = imported_module
            except ImportError:
                logger.warning(f"Could not import {module}")
        
        # Capture stdout and stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        execution_result = {
            "success": True,
            "output": "",
            "error": "",
            "business_results": {},
            "code_executed": code
        }
        
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                # Execute the code
                exec(code, execution_globals)
                
                # Capture output
                execution_result["output"] = stdout_buffer.getvalue()
                
                # Capture any error output
                stderr_content = stderr_buffer.getvalue()
                if stderr_content:
                    execution_result["error"] = stderr_content
                
                # Capture business results (excluding built-ins and imports)
                business_results = {}
                for name, value in execution_globals.items():
                    if (not name.startswith('_') and 
                        name not in safe_imports.values() and
                        name != '__builtins__'):
                        try:
                            # Convert results to business-friendly format
                            if isinstance(value, (int, float, str, bool, list, dict, tuple)):
                                business_results[name] = value
                            elif hasattr(value, 'to_dict'):  # pandas dataframes
                                business_results[name] = value.to_dict('records')
                            elif hasattr(value, 'tolist'):  # numpy arrays
                                business_results[name] = value.tolist()
                            else:
                                business_results[name] = str(value)
                        except Exception:
                            business_results[name] = f"Result: {type(value).__name__}"
                
                execution_result["business_results"] = business_results
                
        except Exception as e:
            execution_result["success"] = False
            execution_result["error"] = f"Execution error: {str(e)}\n{traceback.format_exc()}"
            execution_result["output"] = stdout_buffer.getvalue()
        
        return execution_result
        
    except Exception as e:
        logger.error(f"Code execution tool failed: {e}")
        return {
            "success": False,
            "error": f"Tool execution failed: {str(e)}",
            "output": "",
            "business_results": {}
        }