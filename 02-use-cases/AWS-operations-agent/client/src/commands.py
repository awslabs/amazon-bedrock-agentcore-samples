"""
Simple command handlers
"""
import os
from conversation import ConversationManager
from mcp_tools import MCPTools
import config

class Commands:
    """Simple command handlers"""
    
    def __init__(self, conversation: ConversationManager, mcp: MCPTools):
        self.conversation = conversation
        self.mcp = mcp
        self.temperature = config.DEFAULT_TEMPERATURE
        self.max_tokens = config.DEFAULT_MAX_TOKENS
        self.current_conversation_id = None
    
    def handle_command(self, user_input: str) -> bool:
        """Handle user command, return False to quit"""
        parts = user_input.split()
        cmd = parts[0].lower()
        
        if cmd in ['/quit', '/exit']:
            return False
        
        elif cmd == '/help':
            self._show_help()
        
        elif cmd == '/history':
            self._show_history()
        
        elif cmd == '/clear':
            self._clear_conversation()
        
        elif cmd == '/clear-history':
            self._clear_all_conversations()
        
        elif cmd == '/temp':
            self._set_temperature(parts)
        
        elif cmd == '/max-tokens':
            self._set_max_tokens(parts)
        
        elif cmd == '/token':
            self._set_token()
        
        elif cmd == '/token-file':
            self._set_token_file(parts)
        
        elif cmd == '/tools':
            self.mcp.list_tools()
        
        elif cmd == '/conv':
            self._set_conversation_id(parts)
        
        else:
            print(f"⚠️  Unknown command: {cmd}")
        
        return True
    
    def _show_help(self):
        print("\n📋 Commands:")
        print("  /quit, /exit - Quit")
        print("  /help - Show this help")
        print("  /conv <id> - Set conversation ID")
        print("  /history - List all conversations")
        print("  /clear - Clear current conversation")
        print("  /clear-history - Clear all conversations")
        print(f"  /temp <0.0-1.0> - Set temperature (current: {self.temperature})")
        print(f"  /max-tokens <1-8192> - Set max tokens (current: {self.max_tokens})")
        print("  /token - Enter Okta token")
        print("  /token-file <path> - Load token from file")
        print("  /tools - List MCP tools")
        print()
    
    def _show_history(self):
        print("📜 Fetching conversation list...")
        result = self.conversation.list_conversations()
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return
        
        conversations = result.get("conversations", [])
        if not conversations:
            print("📭 No conversations found")
            return
        
        print(f"📊 Found {len(conversations)} conversations:")
        for conv in conversations:
            conv_id = conv.get('conversation_id', 'unknown')
            updated = conv.get('updated_at', 'unknown')
            count = conv.get('message_count', 0)
            print(f"  • {conv_id} ({count} messages, {updated})")
    
    def _clear_conversation(self):
        if not self.current_conversation_id:
            print("⚠️  No conversation ID set. Use /conv <id> first")
            return
        
        print(f"🗑️  Clearing conversation {self.current_conversation_id}...")
        result = self.conversation.clear_conversation(self.current_conversation_id)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Conversation cleared")
    
    def _clear_all_conversations(self):
        print("🗑️  Clearing ALL conversations...")
        result = self.conversation.clear_all_conversations()
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            count = result.get('deleted_count', 0)
            print(f"✅ Cleared {count} conversations")
    
    def _set_temperature(self, parts):
        if len(parts) < 2:
            print(f"🌡️  Current temperature: {self.temperature}")
            return
        
        try:
            temp = float(parts[1])
            if 0.0 <= temp <= 1.0:
                self.temperature = temp
                print(f"🌡️  Temperature set to {temp}")
            else:
                print("⚠️  Temperature must be 0.0-1.0")
        except ValueError:
            print("⚠️  Invalid temperature")
    
    def _set_max_tokens(self, parts):
        if len(parts) < 2:
            print(f"🔢 Current max tokens: {self.max_tokens}")
            return
        
        try:
            tokens = int(parts[1])
            if 1 <= tokens <= 8192:
                self.max_tokens = tokens
                print(f"🔢 Max tokens set to {tokens}")
            else:
                print("⚠️  Max tokens must be 1-8192")
        except ValueError:
            print("⚠️  Invalid max tokens")
    
    def _set_token(self):
        print("🔑 Enter Okta token:")
        try:
            token = input().strip()
            if token:
                self.mcp.set_token(token)
            else:
                print("⚠️  No token provided")
        except (EOFError, KeyboardInterrupt):
            print("⚠️  Cancelled")
    
    def _set_token_file(self, parts):
        if len(parts) < 2:
            print(f"⚠️  Usage: /token-file <path>")
            return
        
        try:
            with open(parts[1], 'r') as f:
                token = f.read().strip()
            if token:
                self.mcp.set_token(token)
            else:
                print("⚠️  Empty token file")
        except Exception as e:
            print(f"❌ Error reading file: {e}")
    
    def _set_conversation_id(self, parts):
        if len(parts) < 2:
            print(f"💬 Current conversation ID: {self.current_conversation_id or 'None'}")
            print("   Usage: /conv <id>")
            return
        
        self.current_conversation_id = parts[1]
        print(f"💬 Conversation ID set to: {self.current_conversation_id}")
    
    def get_settings(self):
        """Get current settings for message sending"""
        return {
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'conversation_id': self.current_conversation_id,
            'okta_token': self.mcp.okta_token
        }
