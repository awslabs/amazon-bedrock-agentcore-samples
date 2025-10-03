import boto3
import uuid
from typing import Dict, Optional
from dataclasses import dataclass
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from botocore.exceptions import ClientError
from ..config import Configuration


@dataclass
class MemoryConfig:
    """Configuration for agent memory integration."""
    memory_id: str
    memory_client: MemoryClient
    session_id: str
    actor_id: str
    namespace: str


class MarketingMemoryManager:
    """Manages AgentCore Memory lifecycle for marketing research agents."""
    
    def __init__(self, config: Configuration):
        self.config = config
        self.memory_client = MemoryClient(region_name=config.aws_region)
        self._memory_id: Optional[str] = None
        self._session_id: Optional[str] = None
        self._actor_ids: Dict[str, str] = {}
    
    def initialize_memory(self) -> str:
        """Initialize AgentCore Memory resources using boto3 SDK."""
        memory_name = "MarketingResearchAgentMemory"
        
        try:
            # First, check if memory already exists
            memories = list(self.memory_client.list_memories())
            print(f"Found {len(memories)} existing memories")
            
            # Debug: print all memory details
            for memory in memories:
                print(f"  Memory Name: {memory.get('name')} | ID: {memory.get('id')} | Status: {memory.get('status')}")
            
            # Look for existing memory by name first, then by ID pattern
            existing_memory = None
            for m in memories:
                # Check by name first (most reliable)
                if m.get('name') == memory_name:
                    existing_memory = m
                    print(f"Found memory by name: {memory_name}")
                    break
                # Fallback: check by ID pattern
                elif memory_name in m.get('id', ''):
                    existing_memory = m
                    print(f"Found memory by ID pattern: {m.get('id')}")
                    break
            
            if existing_memory:
                self._memory_id = existing_memory.get("id")
                memory_status = existing_memory.get("status", "UNKNOWN")
                print(f"Using existing memory: {memory_name} (ID: {self._memory_id}, Status: {memory_status})")
                
                # Check if memory is in ACTIVE state
                if memory_status == "ACTIVE":
                    print(f"✓ Memory {self._memory_id} is ACTIVE and ready to use")
                    return self._memory_id
                elif memory_status in ["CREATING", "UPDATING"]:
                    print(f"⚠ Memory {self._memory_id} is in {memory_status} state, will use it anyway")
                    return self._memory_id
                else:
                    print(f"⚠ Memory {self._memory_id} is in {memory_status} state")
                    # Try to use it anyway, but log the status
                    return self._memory_id
            
            # If no existing memory found, create a new one
            print(f"No existing memory found with name '{memory_name}', creating new one...")
            
            try:
                memory_response = self.memory_client.create_memory_and_wait(
                    name=memory_name,
                    description="Memory for marketing research agent system with competitive intelligence and team preferences",
                    strategies=[
                        {
                            StrategyType.SEMANTIC.value: {
                                "name": "MarketIntelligence",
                                "description": "Captures market research facts and competitor intelligence",
                                "namespaces": ["marketing/{actorId}/intelligence"]
                            }
                        },
                        {
                            StrategyType.USER_PREFERENCE.value: {
                                "name": "TeamPreferences", 
                                "description": "Tracks marketing team preferences and methodologies",
                                "namespaces": ["marketing/{actorId}/preferences"]
                            }
                        },
                        {
                            StrategyType.SUMMARY.value: {
                                "name": "SessionSummaries",
                                "description": "Creates summaries of research sessions and findings",
                                "namespaces": ["marketing/{actorId}/summaries/{sessionId}"]
                            }
                        }
                    ],
                    event_expiry_days=7,
                    max_wait=300,
                    poll_interval=10
                )
                
                self._memory_id = memory_response.get("id")
                print(f"✓ Created new memory: {memory_name} (ID: {self._memory_id})")
                return self._memory_id
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = str(e)
                
                if "already exists" in error_message or error_code == 'ConflictException':
                    print(f"Memory creation failed because it already exists. Retrying memory lookup...")
                    # Refresh the memory list and try again
                    memories = list(self.memory_client.list_memories())
                    for m in memories:
                        if m.get('name') == memory_name or memory_name in m.get('id', ''):
                            self._memory_id = m.get("id")
                            print(f"✓ Found existing memory on retry: {memory_name} (ID: {self._memory_id})")
                            return self._memory_id
                    
                    # If we still can't find it, raise the original error
                    print(f"❌ Could not find memory after creation conflict")
                    raise e
                else:
                    print(f"❌ Memory creation failed with error: {error_code} - {error_message}")
                    raise e
            
        except Exception as e:
            print(f"❌ Memory initialization error: {e}")
            import traceback
            traceback.print_exc()
            raise e
    
    def get_memory_config_for_agent(self, agent_type: str) -> MemoryConfig:
        """Provide memory configuration to individual agents."""
        if not self._memory_id:
            raise ValueError("Memory not initialized. Call initialize_memory() first.")
        
        if not self._session_id:
            self._session_id = self._generate_session_id()
        
        if agent_type not in self._actor_ids:
            self._actor_ids[agent_type] = self._generate_actor_id(agent_type)
        
        # Define namespace based on agent type
        namespace_map = {
            "supervisor": "marketing/{actorId}/coordination",
            "research": "marketing/{actorId}/intelligence", 
            "database": "marketing/{actorId}/customer_insights",
            "code_generator": "marketing/{actorId}/analytics",
            "reporting": "marketing/{actorId}/reports"
        }
        
        namespace_template = namespace_map.get(agent_type, "marketing/{actorId}/general")
        namespace = namespace_template.format(actorId=self._actor_ids[agent_type])
        
        return MemoryConfig(
            memory_id=self._memory_id,
            memory_client=self.memory_client,
            session_id=self._session_id,
            actor_id=self._actor_ids[agent_type],
            namespace=namespace
        )
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID for each research session."""
        return f"marketing_session_{uuid.uuid4().hex[:8]}"
    
    def _generate_actor_id(self, agent_type: str) -> str:
        """Generate unique actor ID for each agent type."""
        return f"{agent_type}_agent_{uuid.uuid4().hex[:8]}"
    
    def validate_memory_access(self) -> bool:
        """Validate that memory is accessible and can be used."""
        if not self._memory_id:
            print("❌ No memory ID available for validation")
            return False
        
        try:
            # Test basic memory access
            memories = list(self.memory_client.list_memories())
            target_memory = next((m for m in memories if m.get('id') == self._memory_id), None)
            
            if not target_memory:
                print(f"❌ Memory {self._memory_id} not found in memory list")
                return False
            
            print(f"✓ Memory found: {target_memory.get('name')} (Status: {target_memory.get('status')})")
            
            # Test event creation with a validation message
            test_actor_id = f"validation_actor_{uuid.uuid4().hex[:8]}"
            test_session_id = f"validation_session_{uuid.uuid4().hex[:8]}"
            
            self.memory_client.create_event(
                memory_id=self._memory_id,
                actor_id=test_actor_id,
                session_id=test_session_id,
                messages=[
                    ("This is a validation test message", "USER"),
                    ("Memory validation successful", "ASSISTANT")
                ]
            )
            
            print("✓ Memory event creation test successful")
            
            # Test event retrieval
            events = self.memory_client.list_events(
                memory_id=self._memory_id,
                actor_id=test_actor_id,
                session_id=test_session_id,
                max_results=5
            )
            
            if events:
                print("✓ Memory event retrieval test successful")
            else:
                print("⚠ Memory event retrieval returned no results (may be expected)")
            
            return True
            
        except Exception as e:
            print(f"❌ Memory validation failed: {e}")
            import traceback
            traceback.print_exc()
            return False