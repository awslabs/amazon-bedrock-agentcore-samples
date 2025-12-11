"""
Updated Strands to OpenInference Converter for Arize AI

This module provides a span processor that correctly converts Strands telemetry data
to OpenInference format, updated for the new OpenTelemetry GenAI semantic conventions.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.trace import Span

logger = logging.getLogger(__name__)

class StrandsToOpenInferenceProcessor(SpanProcessor):
    """
    SpanProcessor that converts Strands telemetry attributes to OpenInference format
    for compatibility with Arize AI, updated for new OpenTelemetry GenAI conventions.
    """

    def __init__(self, debug: bool = False):
        """
        Initialize the processor.
        
        Args:
            debug: Whether to log debug information
        """
        super().__init__()
        self.debug = debug
        self.processed_spans = set()
        self.current_cycle_id = None
        self.span_hierarchy = {}

    def on_start(self, span, parent_context=None):
        """Called when a span is started. Track span hierarchy."""
        span_id = span.get_span_context().span_id
        parent_id = None
        
        if parent_context and hasattr(parent_context, 'span_id'):
            parent_id = parent_context.span_id
        elif span.parent and hasattr(span.parent, 'span_id'):
            parent_id = span.parent.span_id
            
        self.span_hierarchy[span_id] = {
            'name': span.name,
            'span_id': span_id,
            'parent_id': parent_id,
            'start_time': datetime.now().isoformat()
        }

    def on_end(self, span: Span):
        """
        Called when a span ends. Transform the span attributes from Strands format
        to OpenInference format.
        """
        if not hasattr(span, '_attributes') or not span._attributes:
            return

        original_attrs = dict(span._attributes)
        span_id = span.get_span_context().span_id
        
        if span_id in self.span_hierarchy:
            self.span_hierarchy[span_id]['attributes'] = original_attrs
        
        try:
            if "event_loop.cycle_id" in original_attrs:
                self.current_cycle_id = original_attrs.get("event_loop.cycle_id")
            
            # Extract events if available
            events = []
            if hasattr(span, '_events'):
                events = span._events
            elif hasattr(span, 'events'):
                events = span.events
                
            transformed_attrs = self._transform_attributes(original_attrs, span, events)
            span._attributes.clear()
            span._attributes.update(transformed_attrs)
            self.processed_spans.add(span_id)
            
            if self.debug:
                logger.info(f"Transformed span '{span.name}': {len(original_attrs)} -> {len(transformed_attrs)} attributes")
                logger.info(f"Processed {len(events)} events")
                
        except Exception as e:
            logger.error(f"Failed to transform span '{span.name}': {e}", exc_info=True)
            span._attributes.clear()
            span._attributes.update(original_attrs)

    def _transform_attributes(self, attrs: Dict[str, Any], span: Span, events: List = None) -> Dict[str, Any]:
        """
        Transform Strands attributes to OpenInference format, including event processing.
        """
        result = {}
        span_kind = self._determine_span_kind(span, attrs)
        result["openinference.span.kind"] = span_kind
        self._set_graph_node_attributes(span, attrs, result)
        
        # Extract messages from events if available, otherwise fall back to attributes
        if events and len(events) > 0:
            input_messages, output_messages = self._extract_messages_from_events(events)
        else:
            # Fallback to attribute-based extraction
            prompt = attrs.get("gen_ai.prompt")
            completion = attrs.get("gen_ai.completion")
            if prompt or completion:
                input_messages, output_messages = self._extract_messages_from_attributes(prompt, completion)
            else:
                input_messages, output_messages = [], []
        
        model_id = attrs.get("gen_ai.request.model")
        agent_name = attrs.get("agent.name") or attrs.get("gen_ai.agent.name")

        if model_id:
            result["llm.model_name"] = model_id
            result["gen_ai.request.model"] = model_id
            
        if agent_name:
            result["llm.system"] = "strands-agents"
            result["llm.provider"] = "strands-agents"
        
        # Handle tags (both Strands arize.tags and standard tag.tags)
        self._handle_tags(attrs, result)
        
        # Handle different span types
        if span_kind in ["LLM", "AGENT", "CHAIN"]:
            self._handle_llm_span(attrs, result, input_messages, output_messages)
        elif span_kind == "TOOL":
            self._handle_tool_span(attrs, result, events)
        
        # Handle token usage
        self._map_token_usage(attrs, result)
        
        # Important attributes
        important_attrs = [
            "session.id", "user.id", "llm.prompt_template.template",
            "llm.prompt_template.version", "llm.prompt_template.variables",
            "gen_ai.event.start_time", "gen_ai.event.end_time"
        ]
        
        for key in important_attrs:
            if key in attrs:
                result[key] = attrs[key]
        
        self._add_metadata(attrs, result)    
        return result

    def _extract_messages_from_events(self, events: List) -> tuple[List[Dict], List[Dict]]:
        """Extract input and output messages from Strands events with updated format handling."""
        input_messages = []
        output_messages = []
        
        for event in events:
            event_name = getattr(event, 'name', '') if hasattr(event, 'name') else event.get('name', '')
            event_attrs = getattr(event, 'attributes', {}) if hasattr(event, 'attributes') else event.get('attributes', {})
            
            if event_name == "gen_ai.user.message":
                content = event_attrs.get('content', '')
                message = self._parse_message_content(content, 'user')
                if message:
                    input_messages.append(message)
                    
            elif event_name == "gen_ai.assistant.message":
                content = event_attrs.get('content', '')
                message = self._parse_message_content(content, 'assistant')
                if message:
                    output_messages.append(message)
                    
            elif event_name == "gen_ai.choice":
                # Final response from the agent
                message_content = event_attrs.get('message', '')
                if message_content:
                    message = self._parse_message_content(message_content, 'assistant')
                    if message:
                        # Set finish reason if available
                        if 'finish_reason' in event_attrs:
                            message['message.finish_reason'] = event_attrs['finish_reason']
                        output_messages.append(message)
                        
            elif event_name == "gen_ai.tool.message":
                # Tool messages - treat as user messages with tool role
                content = event_attrs.get('content', '')
                tool_id = event_attrs.get('id', '')
                if content:
                    message = self._parse_message_content(content, 'tool')
                    if message and tool_id:
                        message['message.tool_call_id'] = tool_id
                        input_messages.append(message)
        
        return input_messages, output_messages

    def _extract_messages_from_attributes(self, prompt: Any, completion: Any) -> tuple[List[Dict], List[Dict]]:
        """Fallback method to extract messages from attributes."""
        input_messages = []
        output_messages = []
        
        if prompt:
            if isinstance(prompt, str):
                try:
                    prompt_data = json.loads(prompt)
                    if isinstance(prompt_data, list):
                        for msg in prompt_data:
                            normalized = self._normalize_message(msg)
                            if normalized.get('message.role') == 'user':
                                input_messages.append(normalized)
                except json.JSONDecodeError:
                    # Simple string prompt
                    input_messages.append({
                        'message.role': 'user',
                        'message.content': str(prompt)
                    })
        
        if completion:
            if isinstance(completion, str):
                try:
                    completion_data = json.loads(completion)
                    if isinstance(completion_data, list):
                        # Handle Strands completion format
                        message = self._parse_strands_completion(completion_data)
                        if message:
                            output_messages.append(message)
                except json.JSONDecodeError:
                    # Simple string completion
                    output_messages.append({
                        'message.role': 'assistant',
                        'message.content': str(completion)
                    })
        
        return input_messages, output_messages

    def _parse_message_content(self, content: str, role: str) -> Optional[Dict]:
        """Parse message content from Strands event format with enhanced JSON parsing."""
        if not content:
            return None
            
        try:
            # Try to parse as JSON first
            content_data = json.loads(content) if isinstance(content, str) else content
            
            if isinstance(content_data, list):
                # New Strands format: [{"text": "..."}, {"toolUse": {...}}, {"toolResult": {...}}]
                message = {
                    'message.role': role,
                    'message.content': '',
                    'message.tool_calls': []
                }
                
                text_parts = []
                for item in content_data:
                    if isinstance(item, dict):
                        if 'text' in item:
                            text_parts.append(str(item['text']))
                        elif 'toolUse' in item:
                            tool_use = item['toolUse']
                            tool_call = {
                                'tool_call.id': tool_use.get('toolUseId', ''),
                                'tool_call.function.name': tool_use.get('name', ''),
                                'tool_call.function.arguments': json.dumps(tool_use.get('input', {}))
                            }
                            message['message.tool_calls'].append(tool_call)
                        elif 'toolResult' in item:
                            # Handle tool results - extract text content
                            tool_result = item['toolResult']
                            if 'content' in tool_result:
                                if isinstance(tool_result['content'], list):
                                    for tr_content in tool_result['content']:
                                        if isinstance(tr_content, dict) and 'text' in tr_content:
                                            text_parts.append(str(tr_content['text']))
                                elif isinstance(tool_result['content'], str):
                                    text_parts.append(tool_result['content'])
                            # Set role to tool for tool results and include tool call ID
                            message['message.role'] = 'tool'
                            if 'toolUseId' in tool_result:
                                message['message.tool_call_id'] = tool_result['toolUseId']
                
                message['message.content'] = ' '.join(text_parts) if text_parts else ''
                
                # Clean up empty tool_calls
                if not message['message.tool_calls']:
                    del message['message.tool_calls']
                
                return message
            elif isinstance(content_data, dict):
                # Handle single dict format (like tool messages)
                if 'text' in content_data:
                    return {
                        'message.role': role,
                        'message.content': str(content_data['text'])
                    }
                else:
                    return {
                        'message.role': role,
                        'message.content': str(content_data)
                    }
            else:
                # Simple string content
                return {
                    'message.role': role,
                    'message.content': str(content_data)
                }
                
        except (json.JSONDecodeError, TypeError):
            # Fallback to string content
            return {
                'message.role': role,
                'message.content': str(content)
            }

    def _parse_strands_completion(self, completion_data: List[Any]) -> Optional[Dict]:
        """Parse Strands completion format into a message."""
        message = {
            'message.role': 'assistant',
            'message.content': '',
            'message.tool_calls': []
        }
        
        text_parts = []
        for item in completion_data:
            if isinstance(item, dict):
                if 'text' in item:
                    text_parts.append(str(item['text']))
                elif 'toolUse' in item:
                    tool_use = item['toolUse']
                    tool_call = {
                        'tool_call.id': tool_use.get('toolUseId', ''),
                        'tool_call.function.name': tool_use.get('name', ''),
                        'tool_call.function.arguments': json.dumps(tool_use.get('input', {}))
                    }
                    message['message.tool_calls'].append(tool_call)
        
        message['message.content'] = ' '.join(text_parts) if text_parts else ''
        
        # Clean up empty arrays
        if not message['message.tool_calls']:
            del message['message.tool_calls']
        
        return message if message['message.content'] or 'message.tool_calls' in message else None

    def _handle_llm_span(self, attrs: Dict[str, Any], result: Dict[str, Any], 
                        input_messages: List[Dict], output_messages: List[Dict]):
        """Handle LLM/Agent span with extracted messages."""
        
        # Create message arrays
        if input_messages:
            result["llm.input_messages"] = json.dumps(input_messages, separators=(",", ":"))
            self._flatten_messages(input_messages, "llm.input_messages", result)
        
        if output_messages:
            result["llm.output_messages"] = json.dumps(output_messages, separators=(",", ":"))
            self._flatten_messages(output_messages, "llm.output_messages", result)
        
        # Handle agent tools
        if tools := (attrs.get("gen_ai.agent.tools") or attrs.get("agent.tools")):
            self._map_tools(tools, result)
        
        # Create input/output values
        self._create_input_output_values(attrs, result, input_messages, output_messages)
        
        # Map invocation parameters
        self._map_invocation_parameters(attrs, result)

    def _flatten_messages(self, messages: List[Dict], key_prefix: str, result: Dict[str, Any]):
        """Flatten message structure for OpenInference."""
        for idx, msg in enumerate(messages):
            for key, value in msg.items():
                clean_key = key.replace("message.", "") if key.startswith("message.") else key
                dotted_key = f"{key_prefix}.{idx}.message.{clean_key}"
                
                if clean_key == "tool_calls" and isinstance(value, list):
                    # Handle tool calls
                    for tool_idx, tool_call in enumerate(value):
                        if isinstance(tool_call, dict):
                            for tool_key, tool_val in tool_call.items():
                                tool_dotted_key = f"{key_prefix}.{idx}.message.tool_calls.{tool_idx}.{tool_key}"
                                result[tool_dotted_key] = self._serialize_value(tool_val)
                else:
                    result[dotted_key] = self._serialize_value(value)

    def _create_input_output_values(self, attrs: Dict[str, Any], result: Dict[str, Any],
                                   input_messages: List[Dict], output_messages: List[Dict]):
        """Create input.value and output.value for Arize compatibility."""
        span_kind = result.get("openinference.span.kind")
        model_name = result.get("llm.model_name") or attrs.get("gen_ai.request.model") or "unknown"
        
        if span_kind in ["LLM", "AGENT", "CHAIN"]:
            # Create input.value
            if input_messages:
                if len(input_messages) == 1 and input_messages[0].get('message.role') == 'user':
                    # Simple user message
                    result["input.value"] = input_messages[0].get('message.content', '')
                    result["input.mime_type"] = "text/plain"
                else:
                    # Complex conversation
                    input_structure = {
                        "messages": input_messages,
                        "model": model_name
                    }
                    result["input.value"] = json.dumps(input_structure, separators=(",", ":"))
                    result["input.mime_type"] = "application/json"
            
            # Create output.value  
            if output_messages:
                last_message = output_messages[-1]
                content = last_message.get('message.content', '')
                
                if span_kind == "LLM":
                    # LLM format
                    output_structure = {
                        "choices": [{
                            "finish_reason": last_message.get('message.finish_reason', 'stop'),
                            "index": 0,
                            "message": {
                                "content": content,
                                "role": last_message.get('message.role', 'assistant')
                            }
                        }],
                        "model": model_name,
                        "usage": {
                            "completion_tokens": result.get("llm.token_count.completion"),
                            "prompt_tokens": result.get("llm.token_count.prompt"),
                            "total_tokens": result.get("llm.token_count.total")
                        }
                    }
                    result["output.value"] = json.dumps(output_structure, separators=(",", ":"))
                    result["output.mime_type"] = "application/json"
                else:
                    # Simple text output for AGENT/CHAIN
                    result["output.value"] = content
                    result["output.mime_type"] = "text/plain"

    def _handle_tags(self, attrs: Dict[str, Any], result: Dict[str, Any]):
        """Handle both Strands arize.tags and standard tag.tags formats."""
        tags = None
        
        # Check for Strands format first
        if "arize.tags" in attrs:
            tags = attrs["arize.tags"]
        elif "tag.tags" in attrs:
            tags = attrs["tag.tags"]
        
        if tags:
            if isinstance(tags, list):
                result["tag.tags"] = tags
            elif isinstance(tags, str):
                result["tag.tags"] = [tags]

    def _determine_span_kind(self, span: Span, attrs: Dict[str, Any]) -> str:
        """Determine the OpenInference span kind with updated naming conventions."""
        span_name = span.name
        
        # Handle new span naming conventions
        if span_name == "chat":
            return "LLM"
        elif span_name.startswith("execute_tool "):
            return "TOOL"
        elif span_name == "execute_event_loop_cycle":
            return "CHAIN"
        elif span_name.startswith("invoke_agent"):
            return "AGENT"
        # Legacy support for old naming
        elif "Model invoke" in span_name:
            return "LLM"
        elif span_name.startswith("Tool:"):
            return "TOOL"
        elif "Cycle" in span_name:
            return "CHAIN"
        elif attrs.get("gen_ai.agent.name") or attrs.get("agent.name"):
            return "AGENT"
        
        return "CHAIN"
    
    def _set_graph_node_attributes(self, span: Span, attrs: Dict[str, Any], result: Dict[str, Any]):
        """Set graph node attributes for Arize visualization with updated span names."""
        span_name = span.name
        span_kind = result["openinference.span.kind"]        
        span_id = span.get_span_context().span_id
        
        # Get parent information from span hierarchy
        span_info = self.span_hierarchy.get(span_id, {})
        parent_id = span_info.get('parent_id')
        parent_info = self.span_hierarchy.get(parent_id, {}) if parent_id else {}
        parent_name = parent_info.get('name', '')
        
        if span_kind == "AGENT":
            result["graph.node.id"] = "strands_agent"
        elif span_kind == "CHAIN":
            if span_name == "execute_event_loop_cycle":
                cycle_id = attrs.get("event_loop.cycle_id", f"cycle_{span_id}")
                result["graph.node.id"] = f"cycle_{cycle_id}"
                result["graph.node.parent_id"] = "strands_agent"
            elif "Cycle " in span_name:  # Legacy support
                cycle_id = span_name.replace("Cycle ", "").strip()
                result["graph.node.id"] = f"cycle_{cycle_id}"
                result["graph.node.parent_id"] = "strands_agent"
        elif span_kind == "LLM":
            result["graph.node.id"] = f"llm_{span_id}"
            if parent_name == "execute_event_loop_cycle" or parent_name.startswith("Cycle"):
                parent_cycle_id = parent_info.get('attributes', {}).get('event_loop.cycle_id')
                if parent_cycle_id:
                    result["graph.node.parent_id"] = f"cycle_{parent_cycle_id}"
                else:
                    result["graph.node.parent_id"] = "strands_agent"
            else:
                result["graph.node.parent_id"] = "strands_agent"
        elif span_kind == "TOOL":
            tool_name = span_name.replace("execute_tool ", "") if span_name.startswith("execute_tool ") else "unknown_tool"
            result["graph.node.id"] = f"tool_{tool_name}_{span_id}"
            if parent_name == "execute_event_loop_cycle" or parent_name.startswith("Cycle"):
                parent_cycle_id = parent_info.get('attributes', {}).get('event_loop.cycle_id')
                if parent_cycle_id:
                    result["graph.node.parent_id"] = f"cycle_{parent_cycle_id}"
                else:
                    result["graph.node.parent_id"] = "strands_agent"
            else:
                result["graph.node.parent_id"] = "strands_agent"

    def _handle_tool_span(self, attrs: Dict[str, Any], result: Dict[str, Any], events: List = None):
        """Handle tool-specific attributes with enhanced event processing."""
        # Extract tool information
        tool_name = attrs.get("gen_ai.tool.name")
        tool_call_id = attrs.get("gen_ai.tool.call.id")
        tool_status = attrs.get("tool.status")
        
        if tool_name:
            result["tool.name"] = tool_name
            
        if tool_call_id:
            result["tool.call_id"] = tool_call_id
            
        if tool_status:
            result["tool.status"] = tool_status
        
        # Extract tool parameters and input/output from events if available
        if events:
            tool_parameters = None
            tool_output = None
            
            for event in events:
                event_name = getattr(event, 'name', '') if hasattr(event, 'name') else event.get('name', '')
                event_attrs = getattr(event, 'attributes', {}) if hasattr(event, 'attributes') else event.get('attributes', {})
                
                if event_name == "gen_ai.tool.message":
                    # Tool input - extract parameters for tool.parameters attribute
                    content = event_attrs.get('content', '')
                    if content:
                        try:
                            content_data = json.loads(content) if isinstance(content, str) else content
                            if isinstance(content_data, dict):
                                tool_parameters = content_data
                            else:
                                tool_parameters = {"input": str(content_data)}
                        except (json.JSONDecodeError, TypeError):
                            tool_parameters = {"input": str(content)}
                            
                elif event_name == "gen_ai.choice":
                    # Tool output
                    message = event_attrs.get('message', '')
                    if message:
                        try:
                            message_data = json.loads(message) if isinstance(message, str) else message
                            if isinstance(message_data, list):
                                text_parts = []
                                for item in message_data:
                                    if isinstance(item, dict) and 'text' in item:
                                        text_parts.append(item['text'])
                                tool_output = ' '.join(text_parts) if text_parts else str(message_data)
                            else:
                                tool_output = str(message_data)
                        except (json.JSONDecodeError, TypeError):
                            tool_output = str(message)
            
            # Set the crucial tool.parameters attribute as JSON string
            if tool_parameters:
                result["tool.parameters"] = json.dumps(tool_parameters, separators=(",", ":"))
                
                # Create input messages showing the tool call that triggered this tool execution
                if tool_name and tool_call_id:
                    input_messages = [{
                        'message.role': 'assistant',
                        'message.content': '',
                        'message.tool_calls': [{
                            'tool_call.id': tool_call_id,
                            'tool_call.function.name': tool_name,
                            'tool_call.function.arguments': json.dumps(tool_parameters, separators=(",", ":"))
                        }]
                    }]
                    
                    # Set the flattened input messages for proper display in Arize
                    result["llm.input_messages"] = json.dumps(input_messages, separators=(",", ":"))
                    self._flatten_messages(input_messages, "llm.input_messages", result)
                
                # Also set input.value for display purposes
                if isinstance(tool_parameters, dict):
                    if 'text' in tool_parameters:
                        result["input.value"] = tool_parameters['text']
                        result["input.mime_type"] = "text/plain"
                    else:
                        result["input.value"] = json.dumps(tool_parameters, separators=(",", ":"))
                        result["input.mime_type"] = "application/json"
                        
            if tool_output:
                result["output.value"] = tool_output
                result["output.mime_type"] = "text/plain"

    def _map_tools(self, tools_data: Any, result: Dict[str, Any]):
        """Map tools from Strands to OpenInference format."""
        if isinstance(tools_data, str):
            try:
                tools_data = json.loads(tools_data)
            except json.JSONDecodeError:
                return
        
        if not isinstance(tools_data, list):
            return
        
        # Handle tool names as strings (Strands format)
        for idx, tool in enumerate(tools_data):
            if isinstance(tool, str):
                # Simple tool name
                result[f"llm.tools.{idx}.tool.name"] = tool
                result[f"llm.tools.{idx}.tool.description"] = f"Tool: {tool}"
            elif isinstance(tool, dict):
                # Full tool definition
                result[f"llm.tools.{idx}.tool.name"] = tool.get("name", "")
                result[f"llm.tools.{idx}.tool.description"] = tool.get("description", "")
                if "parameters" in tool or "input_schema" in tool:
                    schema = tool.get("parameters") or tool.get("input_schema")
                    result[f"llm.tools.{idx}.tool.json_schema"] = json.dumps(schema)

    def _map_token_usage(self, attrs: Dict[str, Any], result: Dict[str, Any]):
        """Map token usage metrics."""
        token_mappings = [
            ("gen_ai.usage.prompt_tokens", "llm.token_count.prompt"),
            ("gen_ai.usage.input_tokens", "llm.token_count.prompt"),  # Alternative name
            ("gen_ai.usage.completion_tokens", "llm.token_count.completion"),
            ("gen_ai.usage.output_tokens", "llm.token_count.completion"),  # Alternative name
            ("gen_ai.usage.total_tokens", "llm.token_count.total"),
        ]
        
        for strands_key, openinf_key in token_mappings:
            if value := attrs.get(strands_key):
                result[openinf_key] = value

    def _map_invocation_parameters(self, attrs: Dict[str, Any], result: Dict[str, Any]):
        """Map invocation parameters."""
        params = {}
        param_mappings = {
            "max_tokens": "max_tokens",
            "temperature": "temperature", 
            "top_p": "top_p",
        }
        
        for key, param_key in param_mappings.items():
            if key in attrs:
                params[param_key] = attrs[key]
        
        if params:
            result["llm.invocation_parameters"] = json.dumps(params, separators=(",", ":"))

    def _normalize_message(self, msg: Any) -> Dict[str, Any]:
        """Normalize a single message to OpenInference format."""
        if not isinstance(msg, dict):
            return {"message.role": "user", "message.content": str(msg)}
        
        result = {}
        if "role" in msg:
            result["message.role"] = msg["role"]
        
        # Handle content
        if "content" in msg:
            content = msg["content"]
            if isinstance(content, list):
                # Extract text from content array
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(str(item["text"]))
                result["message.content"] = " ".join(text_parts) if text_parts else ""
            else:
                result["message.content"] = str(content)
        
        return result

    def _add_metadata(self, attrs: Dict[str, Any], result: Dict[str, Any]):
        """Add remaining attributes to metadata."""
        metadata = {}
        skip_keys = {"gen_ai.prompt", "gen_ai.completion", "gen_ai.agent.tools", "agent.tools"}
        
        for key, value in attrs.items():
            if key not in skip_keys and key not in result:
                metadata[key] = self._serialize_value(value)
        
        if metadata:
            result["metadata"] = json.dumps(metadata, separators=(",", ":"))

    def _serialize_value(self, value: Any) -> Any:
        """Ensure a value is serializable."""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        
        try:
            return json.dumps(value, separators=(",", ":"))
        except (TypeError, OverflowError):
            return str(value)

    def shutdown(self):
        """Called when the processor is shutdown."""
        pass

    def force_flush(self, timeout_millis=None):
        """Called to force flush."""
        return True

    @staticmethod
    def get_migration_guide() -> Dict[str, str]:
        """
        Returns a migration guide for updating from deprecated GenAI attributes.
        
        Returns:
            Dict mapping deprecated attributes to their replacements or migration guidance.
        """
        return {
            # Deprecated attributes with replacements
            "gen_ai.usage.prompt_tokens": "gen_ai.usage.input_tokens",
            "gen_ai.usage.completion_tokens": "gen_ai.usage.output_tokens", 
            "gen_ai.openai.request.seed": "gen_ai.request.seed",
            "gen_ai.openai.request.response_format": "gen_ai.output.type",
            
            # Deprecated attributes without direct replacements
            "gen_ai.prompt": "Migrate to event-based messaging using gen_ai.user.message events",
            "gen_ai.completion": "Migrate to event-based messaging using gen_ai.assistant.message and gen_ai.choice events",
            
            # Span naming changes
            "Model invoke": "chat",
            "Cycle [UUID]": "execute_event_loop_cycle",
            "Tool: [name]": "execute_tool [name]",
        }

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Returns information about the processor's capabilities and status.
        
        Returns:
            Dict containing processor information.
        """
        return {
            "processor_name": "StrandsToOpenInferenceProcessor",
            "version": "2.1.0",
            "supports_events": True,
            "supports_deprecated_attributes": True,
            "supports_new_semantic_conventions": True,
            "processed_spans": len(self.processed_spans),
            "debug_enabled": self.debug,
            "migration_guide": self.get_migration_guide(),
            "supported_span_kinds": ["LLM", "AGENT", "CHAIN", "TOOL"],
            "supported_span_names": [
                "chat", "execute_event_loop_cycle", "execute_tool [name]", 
                "invoke_agent [name]", "Model invoke", "Cycle [UUID]", "Tool: [name]"
            ],
            "supported_event_types": [
                "gen_ai.user.message", "gen_ai.assistant.message", 
                "gen_ai.choice", "gen_ai.tool.message"
            ],
            "features": [
                "Event-based message extraction",
                "Enhanced JSON content parsing",
                "Tool result processing",
                "Updated span naming conventions",
                "Deprecated attribute handling with warnings",
                "OpenInference semantic convention compliance",
                "Strands-specific format parsing",
                "Graph node hierarchy mapping",
                "Token usage tracking",
                "Tool call processing",
                "Multi-format content support"
            ]
        }