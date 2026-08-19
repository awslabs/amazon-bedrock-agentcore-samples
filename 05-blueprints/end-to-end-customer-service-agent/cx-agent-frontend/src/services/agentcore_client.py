"""AgentCore client for AWS Bedrock Agent Runtime."""

import requests
import urllib.parse
import json
import uuid


class AgentCoreClient:
    """Client for AWS Bedrock AgentCore Runtime."""

    def __init__(self, agent_runtime_arn: str, region: str, auth_token: str = None):
        self.agent_runtime_arn = agent_runtime_arn
        self.region = region
        self.auth_token = auth_token

    def create_conversation(self, user_id: str) -> str:
        """Create a new conversation session."""
        return str(uuid.uuid4())

    def send_message(
        self, conversation_id: str, message: str, model: str = None, user_id: str = None
    ) -> dict:
        """Send message to AgentCore and get response."""
        try:
            escaped_agent_arn = urllib.parse.quote(self.agent_runtime_arn, safe="")
            url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": conversation_id,
            }

            payload = {
                "input": {
                    "prompt": message,
                    "conversation_id": conversation_id,
                    "jwt_token": self.auth_token,
                }
            }

            if user_id:
                payload["input"]["user_id"] = user_id

            response = requests.post(
                url, headers=headers, data=json.dumps(payload), timeout=61
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "response": result.get("output", {}).get("message", "No response"),
                    "status": "success",
                    "tools_used": [],
                }
            else:
                return {
                    "response": f"Error ({response.status_code}): {response.text}",
                    "status": "error",
                    "tools_used": [],
                }

        except Exception as e:
            return {"response": f"Error: {str(e)}", "status": "error", "tools_used": []}

    def submit_feedback(
        self, run_id: str, session_id: str, score: float, comment: str = ""
    ) -> bool:
        """Submit feedback via AgentCore."""
        try:
            escaped_agent_arn = urllib.parse.quote(self.agent_runtime_arn, safe="")
            url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
            }

            payload = {
                "input": {
                    "feedback": {
                        "run_id": run_id,
                        "session_id": session_id,
                        "score": score,
                        "comment": comment,
                    }
                }
            }

            response = requests.post(
                url, headers=headers, data=json.dumps(payload), timeout=30
            )
            return response.status_code == 200

        except Exception:
            return False
