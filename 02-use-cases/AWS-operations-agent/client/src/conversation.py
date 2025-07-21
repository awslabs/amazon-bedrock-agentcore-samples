"""
Stateless conversation manager - just sends messages to Lambda
Lambda/Strands handles all conversation state
"""
from typing import Iterator, Dict, Any
from lambda_client import LambdaClient
import config

class ConversationManager:
    """Stateless conversation manager"""
    
    def __init__(self, lambda_client: LambdaClient):
        self.lambda_client = lambda_client
    
    def send_message(self, message: str, conversation_id: str, temperature: float = None, 
                    max_tokens: int = None, okta_token: str = None) -> Iterator[str]:
        """
        Send message to Lambda with required conversation_id
        Lambda/Strands handles all conversation state
        """
        payload = {
            "message": message,
            "conversation_id": conversation_id,  # REQUIRED
            "temperature": temperature or config.DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens or config.DEFAULT_MAX_TOKENS,
            "use_tools": True,
            "okta_token": okta_token,
            "bedrock_agentcore_gateway_url": config.BEDROCK_AGENTCORE_GATEWAY_URL  # Include Bedrock AgentCore Gateway URL
        }
        
        return self.lambda_client.send_message_streaming(payload)
    
    def list_conversations(self) -> Dict[str, Any]:
        """Get list of all conversations from Lambda"""
        url = config.get_conversations_url(self.lambda_client.function_url)
        return self.lambda_client.call_api(url, 'GET')
    
    def clear_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Clear specific conversation via Lambda"""
        url = config.get_conversation_clear_url(self.lambda_client.function_url, conversation_id)
        return self.lambda_client.call_api(url, 'POST')
    
    def clear_all_conversations(self) -> Dict[str, Any]:
        """Clear all conversations via Lambda"""
        url = config.get_conversations_url(self.lambda_client.function_url)
        return self.lambda_client.call_api(url, 'DELETE')
