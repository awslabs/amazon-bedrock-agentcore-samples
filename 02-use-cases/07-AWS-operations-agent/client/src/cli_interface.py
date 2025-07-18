"""
AWS Operational Support Agent CLI interface
"""
import time
import uuid
from datetime import datetime
from conversation import ConversationManager
from mcp_tools import MCPTools
from commands import Commands

class CLI:
    """AWS Operational Support Agent command line interface"""
    
    def __init__(self, conversation: ConversationManager, mcp: MCPTools):
        self.conversation = conversation
        self.mcp = mcp
        self.commands = Commands(conversation, mcp)
        
        # Auto-generate conversation ID at startup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.auto_conversation_id = f"chat_{timestamp}_{str(uuid.uuid4())[:8]}"
        self.commands.current_conversation_id = self.auto_conversation_id
    
    def run(self):
        """Run the chat interface"""
        self._print_banner()
        self._display_welcome_message()
        
        try:
            while True:
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    should_continue = self.commands.handle_command(user_input)
                    if not should_continue:
                        print("👋 Goodbye!")
                        break
                    continue
                
                # Send chat message
                self._send_message(user_input)
        
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
    
    def _print_banner(self):
        """Print welcome banner"""
        print("\n" + "=" * 60)
        print("🤖 AWS Operational Support Agent")
        print("=" * 60)
        print("💡 Commands: /help, /conv <id>, /history, /clear, /clear-history, /quit")
        print("🚀 Type your message to start chatting!")
        print("=" * 60)
        print(f"🆔 Auto-generated conversation ID: {self.auto_conversation_id}")
        
        # Check for default token only if no token is already set
        # This avoids fetching tools twice
        if not self.mcp.okta_token:
            import os
            import config
            if os.path.exists(config.DEFAULT_TOKEN_FILE):
                try:
                    with open(config.DEFAULT_TOKEN_FILE, 'r') as f:
                        token = f.read().strip()
                    if token:
                        print(f"🔑 Loading token from {config.DEFAULT_TOKEN_FILE}")
                        self.mcp.set_token(token)
                except:
                    pass
    
    def _display_welcome_message(self):
        """Display welcome message from the agent"""
        welcome_message = """
🤖 Agent: Welcome to the AWS Operations Agent! I'm here to help you manage and inspect your AWS resources using natural language.

I can assist with:
• EC2, S3, Lambda, IAM, RDS, CloudWatch resources
• CloudFormation stacks and deployments
• Cost Explorer analysis and optimization
• Container services (ECS, EKS)
• Messaging services (SNS, SQS)
• And many more AWS services!

Just ask me questions like "List my S3 buckets" or "Show me EC2 instances in us-east-1" to get started.
"""
        print(welcome_message)
    
    def _send_message(self, message: str):
        """Send message and display response"""
        settings = self.commands.get_settings()
        
        print("\n🤖 Agent: ", end="", flush=True)
        
        try:
            start_time = time.time()
            response_text = ""
            
            # Stream response
            for chunk in self.conversation.send_message(
                message=message,
                conversation_id=settings['conversation_id'],
                temperature=settings['temperature'],
                max_tokens=settings['max_tokens'],
                okta_token=settings['okta_token']
            ):
                if chunk.startswith("Error:"):
                    print(f"\n❌ {chunk}")
                    return
                
                print(chunk, end="", flush=True)
                response_text += chunk
            
            # Show stats
            duration = time.time() - start_time
            print(f"\n⏱️  {duration:.2f}s | {len(response_text)} chars | Conv: {settings['conversation_id']}")
            
        except KeyboardInterrupt:
            print("\n⏹️  Interrupted")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print(f"\n❌ Error: {e}")
