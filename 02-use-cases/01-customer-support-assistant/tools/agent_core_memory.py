"""
Tool for managing memories in Bedrock Agent Core Memory Service.

This module provides Bedrock Agent Core Memory capabilities with memory record
creation and retrieval.

Key Features:
------------
1. Event Management:
   • create_event: Store events in memory sessions

2. Memory Record Operations:
   • retrieve_memory_records: Semantic search for extracted memories
   • list_memory_records: List all memory records
   • get_memory_record: Get specific memory record
   • delete_memory_record: Delete memory records

Usage Examples:
--------------
```python
from strands import Agent
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider

# Initialize with required parameters
provider = AgentCoreMemoryToolProvider(
    memory_id="memory-123abc",  # Required
    actor_id="user-456",        # Required
    session_id="session-789",   # Required
    namespace="default",        # Required
)

agent = Agent(tools=provider.tools)

# Create a memory using the default IDs from initialization
agent.tool.agent_core_memory(
    action="RecordMemory",
    payload=[{
        "conversational": {
            "content": {"text": "Hello, how are you?"},
            "role": "USER"
        }
    }]
)

# Search memory records using the default namespace from initialization
agent.tool.agent_core_memory(
    action="RetrieveMemory",
    query="user preferences"
)
```
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

# Use typing_extensions.TypedDict instead of typing.TypedDict for compatibility
try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict  # Fallback for Python 3.12+

import boto3
from botocore.config import Config as BotocoreConfig
from strands import tool
from strands.types.tools import AgentTool


# Define payload structure types for conversational messages
class ConversationalContent(TypedDict):
    """Content structure for conversational messages."""

    text: str


class ConversationalPayload(TypedDict):
    """Structure for conversational messages."""

    content: ConversationalContent
    role: Literal["USER", "ASSISTANT", "TOOL", "OTHER"]


class ConversationalPayloadItem(TypedDict):
    """Conversational payload item wrapper."""

    conversational: ConversationalPayload


# Blob payload can be any type
class BlobPayloadItem(TypedDict):
    """Blob payload item wrapper."""

    blob: Any


# Union type for payload items
PayloadItem = Union[ConversationalPayloadItem, BlobPayloadItem, Dict]

# Event payload is a list of payload items
EventPayload = List[PayloadItem]

# Set up logging
logger = logging.getLogger(__name__)

# Default region if not specified
DEFAULT_REGION = "us-west-2"


class AgentCoreMemoryToolProvider:
    """Provider for Agent Core Memory Service tools."""

    def __init__(
        self,
        memory_id: str,
        actor_id: str,
        session_id: str,
        namespace: str,
        region: Optional[str] = None,
        boto_client_config: Optional[BotocoreConfig] = None,
    ):
        """
        Initialize the Agent Core Memory tool provider.

        Args:
            memory_id: Memory ID to use for operations (required)
            actor_id: Actor ID to use for operations (required)
            session_id: Session ID to use for operations (required)
            namespace: Namespace for memory record operations (required)
            region: AWS region for the service
            boto_client_config: Optional boto client configuration

        Raises:
            ValueError: If any of the required parameters are missing or empty
        """
        # Validate required parameters
        if not memory_id:
            raise ValueError("memory_id is required")
        if not actor_id:
            raise ValueError("actor_id is required")
        if not session_id:
            raise ValueError("session_id is required")
        if not namespace:
            raise ValueError("namespace is required")

        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespace = namespace

        # Set up client configuration with user agent
        if boto_client_config:
            existing_user_agent = getattr(boto_client_config, "user_agent_extra", None)
            # Append 'strands-agents-memory' to existing user_agent_extra or set it if not present
            if existing_user_agent:
                new_user_agent = f"{existing_user_agent} strands-agents-memory"
            else:
                new_user_agent = "strands-agents-memory"
            self.client_config = boto_client_config.merge(
                BotocoreConfig(user_agent_extra=new_user_agent)
            )
        else:
            self.client_config = BotocoreConfig(
                user_agent_extra="strands-agents-memory"
            )

        # Resolve region from parameters, environment, or default
        self.region = region or DEFAULT_REGION

        # Initialize clients with None - they'll be created on first use
        self._data_plane_client = None
        self._control_plane_client = None

    def _init_clients(self, region=None):
        """
        Initialize the service clients.

        Args:
            region: Optional region override. If provided, reinitializes clients with this region.
        """
        # Update region if provided
        if region:
            self.region = region

        # Construct endpoint URLs based on the region
        data_plane_endpoint = f"https://bedrock-agentcore.{self.region}.amazonaws.com"
        control_plane_endpoint = (
            f"https://bedrock-agentcore-control.{self.region}.amazonaws.com"
        )

        # Initialize clients with the appropriate region and endpoints
        self._data_plane_client = boto3.client(
            "bedrock-agentcore",
            region_name=self.region,
            endpoint_url=data_plane_endpoint,
            config=self.client_config,
        )
        self._control_plane_client = boto3.client(
            "bedrock-agentcore-control",  # Agent Core Memory Control Plane
            region_name=self.region,
            endpoint_url=control_plane_endpoint,
            config=self.client_config,
        )

    @property
    def tools(self) -> list[AgentTool]:
        """Extract all @tool decorated methods from this instance."""
        tools = []

        for attr_name in dir(self):
            if attr_name == "tools":
                continue
            attr = getattr(self, attr_name)
            # Also check the original way for regular AgentTool instances
            if isinstance(attr, AgentTool):
                tools.append(attr)

        return tools

    @property
    def data_plane_client(self):
        """Get the data plane service client, initializing if needed."""
        if not self._data_plane_client:
            self._init_clients()
        return self._data_plane_client

    @property
    def control_plane_client(self):
        """Get the control plane client, initializing if needed."""
        if not self._control_plane_client:
            self._init_clients()
        return self._control_plane_client

    @tool
    def agent_core_memory(
        self,
        action: str,
        payload: Optional[EventPayload] = None,
        query: Optional[str] = None,
        memory_record_id: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        region: Optional[str] = None,
    ) -> Dict:
        """
        Work with agent memories - create, search, retrieve, list, and manage memory records.

        This tool helps agents store and access memories, allowing them to remember important
        information across conversations and interactions.

        Key Capabilities:
        - Store new memories (text conversations or structured data)
        - Search for memories using semantic search
        - Browse and list all stored memories
        - Retrieve specific memories by ID
        - Delete unwanted memories

        Supported Actions:
        -----------------
        Memory Management:
        - RecordMemory: Store a new memory (conversation or data)
          Use this when you need to save information for later recall.

        - RetrieveMemory: Find relevant memories using semantic search
          Use this when searching for specific information in memories.
          This is the best action for queries like "find memories about X" or "search for memories related to Y".

        - ListMemories: Browse all stored memories
          Use this to see all available memories without filtering.
          This is useful for getting an overview of what's been stored.

        - GetMemory: Fetch a specific memory by ID
          Use this when you already know the exact memory ID.

        - DeleteMemory: Remove a specific memory
          Use this to delete memories that are no longer needed.

        Args:
            action: The memory operation to perform (see Supported Actions)
            payload: Memory content (required for RecordMemory). Must be a list of objects with specific structure:
                     - For conversational memories: [{"conversational": {"content": {"text": "message"},
                       "role": "USER"}}]
                     - For data memories: [{"blob": {"any": "data"}}]
            query: Search terms for finding relevant memories (required for RetrieveMemory)
            memory_record_id: ID of a specific memory (required for GetMemory, DeleteMemory)
            max_results: Maximum number of results to return (optional)
            next_token: Pagination token (optional)
            region: AWS region (defaults to us-west-2)

        Returns:
            Dict: Response containing the requested memory information or operation status

        Examples:
        --------
        # Store a new conversational memory
        result = agent_core_memory(
            action="RecordMemory",
            payload=[{
                "conversational": {
                    "content": {"text": "User prefers vegetarian pizza with extra cheese"},
                    "role": "USER"
                }
            }]
        )

        # Store a structured data memory
        result = agent_core_memory(
            action="RecordMemory",
            payload=[{
                "blob": {
                    "preferences": {
                        "food": "pizza",
                        "toppings": ["cheese", "mushrooms"],
                        "crust": "thin"
                    }
                }
            }]
        )

        # Search for relevant memories (use this for finding specific information)
        result = agent_core_memory(
            action="RetrieveMemory",
            query="what food preferences does the user have"
        )

        # Browse all stored memories (use this for getting an overview)
        result = agent_core_memory(
            action="ListMemories"
        )

        # Get a specific memory by ID
        result = agent_core_memory(
            action="GetMemory",
            memory_record_id="mr-12345"
        )

        # Delete a specific memory
        result = agent_core_memory(
            action="DeleteMemory",
            memory_record_id="mr-12345"
        )
        """
        try:
            # Use values from initialization
            memory_id = self.memory_id
            actor_id = self.actor_id
            session_id = self.session_id
            namespace = self.namespace

            # Use provided values or defaults for other parameters
            memory_record_id = memory_record_id
            max_results = max_results
            # Handle region override - reinitialize clients if a new region is provided
            if region and region != self.region:
                self._init_clients(region=region)
            else:
                region = self.region

            # Define required parameters for each action
            required_params = {
                # New agent-friendly action names
                "RecordMemory": ["memory_id", "actor_id", "session_id", "payload"],
                "RetrieveMemory": ["memory_id", "namespace", "query"],
                "ListMemories": ["memory_id"],
                "GetMemory": ["memory_id", "memory_record_id"],
                "DeleteMemory": ["memory_id", "memory_record_id", "namespace"],
            }

            # Map new action names to original API actions (internal use only)
            action_mapping = {
                "RecordMemory": "create_event",
                "RetrieveMemory": "retrieve_memory_records",
                "ListMemories": "list_memory_records",
                "GetMemory": "get_memory_record",
                "DeleteMemory": "delete_memory_record",
            }

            # Map the action to the API action
            api_action = action_mapping.get(action, action)

            # Validate action
            if action not in required_params:
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": f"Action '{action}' is not supported. "
                            f"Supported actions: {', '.join(action_mapping.keys())}"
                        }
                    ],
                }

            # Validate required parameters
            if action in required_params:
                missing_params = []
                for param in required_params[action]:
                    param_value = locals().get(param)
                    if not param_value:
                        missing_params.append(param)

                if missing_params:
                    return {
                        "status": "error",
                        "content": [
                            {
                                "text": (
                                    f"The following parameters are required for {action} action: "
                                    f"{', '.join(missing_params)}"
                                )
                            }
                        ],
                    }

            # Execute the appropriate action
            try:
                # Handle action names by mapping to API methods
                if action == "RecordMemory" or api_action == "create_event":
                    response = self.create_event(
                        memory_id=memory_id,
                        actor_id=actor_id,
                        session_id=session_id,
                        payload=payload,
                    )
                    # Extract only the relevant "event" field from the response
                    event_data = (
                        response.get("event", {}) if isinstance(response, dict) else {}
                    )
                    return {
                        "status": "success",
                        "content": [
                            {
                                "text": f"Memory created successfully: {json.dumps(event_data, default=str)}"
                            }
                        ],
                    }
                elif (
                    action == "RetrieveMemory"
                    or api_action == "retrieve_memory_records"
                ):
                    response = self.retrieve_memory_records(
                        memory_id=memory_id,
                        namespace=namespace,
                        search_query=query,
                        max_results=max_results,
                        next_token=next_token,
                    )
                    # Extract only the relevant fields from the response
                    relevant_data = {}
                    if isinstance(response, dict):
                        if "memoryRecordSummaries" in response:
                            relevant_data["memoryRecordSummaries"] = response[
                                "memoryRecordSummaries"
                            ]
                        if "nextToken" in response:
                            relevant_data["nextToken"] = response["nextToken"]

                    return {
                        "status": "success",
                        "content": [
                            {
                                "text": f"Memories retrieved successfully: {json.dumps(relevant_data, default=str)}"
                            }
                        ],
                    }
                elif action == "ListMemories" or api_action == "list_memory_records":
                    response = self.list_memory_records(
                        memory_id=memory_id,
                        namespace=namespace,
                        max_results=max_results,
                        next_token=next_token,
                    )
                    # Extract only the relevant fields from the response
                    relevant_data = {}
                    if isinstance(response, dict):
                        if "memoryRecordSummaries" in response:
                            relevant_data["memoryRecordSummaries"] = response[
                                "memoryRecordSummaries"
                            ]
                        if "nextToken" in response:
                            relevant_data["nextToken"] = response["nextToken"]

                    return {
                        "status": "success",
                        "content": [
                            {
                                "text": f"Memories listed successfully: {json.dumps(relevant_data, default=str)}"
                            }
                        ],
                    }
                elif action == "GetMemory" or api_action == "get_memory_record":
                    response = self.get_memory_record(
                        memory_id=memory_id,
                        memory_record_id=memory_record_id,
                    )
                    # Extract only the relevant "memoryRecord" field from the response
                    memory_record = (
                        response.get("memoryRecord", {})
                        if isinstance(response, dict)
                        else {}
                    )
                    return {
                        "status": "success",
                        "content": [
                            {
                                "text": f"Memory retrieved successfully: {json.dumps(memory_record, default=str)}"
                            }
                        ],
                    }
                elif action == "DeleteMemory" or api_action == "delete_memory_record":
                    response = self.delete_memory_record(
                        memory_id=memory_id,
                        memory_record_id=memory_record_id,
                        namespace=namespace,
                    )
                    # Extract only the relevant "memoryRecordId" field from the response
                    memory_record_id = (
                        response.get("memoryRecordId", "")
                        if isinstance(response, dict)
                        else ""
                    )

                    return {
                        "status": "success",
                        "content": [
                            {"text": f"Memory deleted successfully: {memory_record_id}"}
                        ],
                    }
            except Exception as e:
                error_msg = f"API error: {str(e)}"
                logger.error(error_msg)
                return {"status": "error", "content": [{"text": error_msg}]}

        except Exception as e:
            logger.error(f"Unexpected error in agent_core_memory tool: {str(e)}")
            return {"status": "error", "content": [{"text": str(e)}]}

    def create_event(
        self,
        memory_id: str,
        actor_id: str,
        session_id: str,
        payload: EventPayload,
        event_timestamp: Optional[datetime] = None,
    ) -> Dict:
        """
        Create an event in a memory session.

        Creates a new event record in the specified memory session. Events are immutable
        records that capture interactions or state changes in your application.

        Args:
            memory_id: ID of the memory store
            actor_id: ID of the actor (user, agent, etc.) creating the event
            session_id: ID of the session this event belongs to
            payload: List of event payload items. Each item can be:
                - Conversational message (with enforced structure):
                  {
                    "conversational": {
                      "content": {"text": "Message text"},
                      "role": "USER" | "ASSISTANT" | "TOOL" | "OTHER"
                    }
                  }
                - Blob (any structure):
                  {
                    "blob": <any data>
                  }
            event_timestamp: Optional timestamp for the event (defaults to current time)

        Returns:
            Dict: Response containing the created event details

        Raises:
            ValueError: If required parameters are invalid
            RuntimeError: If the API call fails

        Example:
            ```python
            # Example with conversational payload
            payload = [{
                "conversational": {
                    "content": {"text": "Hello, how are you?"},
                    "role": "USER"
                }
            }]

            # Example with blob payload
            blob_payload = [{
                "blob": {"custom_data": "any structure can go here"}
            }]

            result = create_event(
                memory_id="memory-123abc",
                actor_id="user-456",
                session_id="session-789",
                payload=payload
            )
            ```
        """

        # Set default timestamp if not provided
        if event_timestamp is None:
            event_timestamp = datetime.now(timezone.utc)

        return self.data_plane_client.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=event_timestamp,
            payload=payload,
        )

    def retrieve_memory_records(
        self,
        memory_id: str,
        namespace: str,
        search_query: str,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """
        Retrieve memory records using semantic search.

        Performs a semantic search across memory records in the specified namespace,
        returning records that semantically match the search query. Results are ranked
        by relevance to the query.

        Args:
            memory_id: ID of the memory store to search in
            namespace: Namespace to search within (e.g., "actor/user123/userId")
            search_query: Natural language query to search for
            max_results: Maximum number of results to return (default: service default)
            next_token: Pagination token for retrieving additional results

        Returns:
            Dict: Response containing matching memory records and optional next_token
        """
        # Prepare request parameters
        params = {
            "memoryId": memory_id,
            "namespace": namespace,
            "searchCriteria": {"searchQuery": search_query},
        }
        if max_results is not None:
            params["maxResults"] = max_results
        if next_token is not None:
            params["nextToken"] = next_token

        # Direct API call without redundant try/except block
        return self.data_plane_client.retrieve_memory_records(**params)

    def get_memory_record(
        self,
        memory_id: str,
        memory_record_id: str,
    ) -> Dict:
        """Get a specific memory record."""
        return self.data_plane_client.get_memory_record(
            memoryId=memory_id,
            memoryRecordId=memory_record_id,
        )

    def list_memory_records(
        self,
        memory_id: str,
        namespace: str,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> Dict:
        """List memory records."""
        params = {"memoryId": memory_id}
        if namespace is not None:
            params["namespace"] = namespace
        if max_results is not None:
            params["maxResults"] = max_results
        if next_token is not None:
            params["nextToken"] = next_token
        return self.data_plane_client.list_memory_records(**params)

    def delete_memory_record(
        self,
        memory_id: str,
        memory_record_id: str,
        namespace: str,
    ) -> Dict:
        """Delete a specific memory record."""
        return self.data_plane_client.delete_memory_record(
            memoryId=memory_id,
            memoryRecordId=memory_record_id,
            namespace=namespace,
        )
