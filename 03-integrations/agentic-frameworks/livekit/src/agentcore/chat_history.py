import json
from typing import List, Dict, Any, Optional
from datetime import datetime

class ChatMessage:
    def __init__(self, role: str, content: str, timestamp: Optional[float] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().timestamp()
        self.type = "text"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }

class ChatHistory:
    def __init__(self):
        self.messages: List[ChatMessage] = []
    
    def add_message(self, role: str, content: str) -> ChatMessage:
        message = ChatMessage(role, content)
        self.messages.append(message)
        return message
    
    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "messages": [msg.to_dict() for msg in self.messages]
        }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
