# import pytest
# from unittest.mock import Mock, patch, AsyncMock, MagicMock
# import sys
# from pathlib import Path

# # Add src to path for imports
# sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# # Mock MCP client to prevent Gateway connection attempts
# mock_mcp_client = Mock()
# mock_mcp_client.list_tools_sync.return_value = []
# mock_mcp_client.__enter__ = Mock(return_value=mock_mcp_client)
# mock_mcp_client.__exit__ = Mock(return_value=False)
# with patch('mcp_client.client.get_streamable_http_mcp_client', return_value=mock_mcp_client):
#     from main import app, invoke

# class TestAgent:

#     @patch('main.model')
#     @patch('main.Agent')
#     def test_invoke_with_prompt(self, mock_agent_class, mock_model):
#         """Test invoke function with user prompt"""
#         mock_agent = Mock()
#         mock_agent.return_value = "Test response"
#         mock_agent_class.return_value = mock_agent

#         payload = {"prompt": "Hello, how are you?"}
#         result = invoke(payload)

#         mock_agent.assert_called_once_with("Hello, how are you?")
#         assert result == {"response": "Test response"}

# class TestBedrockAgentCoreApp:
#     def test_app_initialization(self):
#         """Test that BedrockAgentCoreApp is properly initialized"""
#         assert app is not None
#         assert hasattr(app, 'entrypoint')

#     def test_entrypoint_decorator(self):
#         """Test that entrypoint function is properly decorated"""

#         assert hasattr(invoke, '__name__')
#         assert invoke.__name__ == 'invoke'
