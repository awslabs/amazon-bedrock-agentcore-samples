#!/usr/bin/env python3
"""
AWS Operations Agent - Natural language AWS operations via Bedrock AgentCore Gateway
"""
import sys
import argparse
import config
from auth import AWSAuth
from lambda_client import LambdaClient
from mcp_tools import MCPTools
from conversation import ConversationManager
from cli_interface import CLI

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="AWS Operations Agent")
    parser.add_argument("--url", default=config.get_stream_url(config.DEFAULT_FUNCTION_URL), help="Lambda Function URL (with /stream suffix)")
    parser.add_argument("--region", default=config.DEFAULT_REGION, help="AWS region")
    parser.add_argument("--profile", default=config.DEFAULT_PROFILE, help="AWS profile")
    parser.add_argument("--token", help="Okta token")
    parser.add_argument("--token-file", default=config.DEFAULT_TOKEN_FILE, help="Token file path")
    parser.add_argument("--verbose", action="store_true", help="Show verbose configuration")
    
    args = parser.parse_args()
    
    try:
        # Print configuration summary if verbose
        if args.verbose:
            config.print_config_summary()
        else:
            print(f"🔗 Connecting to: {args.url}")
            print(f"🌎 Region: {args.region}, Profile: {args.profile}")
        
        # Initialize components
        auth = AWSAuth(args.region, args.profile)
        lambda_client = LambdaClient(auth, args.url)
        mcp_tools = MCPTools(lambda_client)
        conversation = ConversationManager(lambda_client)
        
        # Set token if provided
        if args.token:
            mcp_tools.set_token(args.token)
        elif args.token_file:
            try:
                with open(args.token_file, 'r') as f:
                    token = f.read().strip()
                if token:
                    mcp_tools.set_token(token)
                    print(f"🔑 Loaded token from {args.token_file}")
            except Exception as e:
                print(f"⚠️  Error reading token file: {e}")
        
        # Start CLI
        cli = CLI(conversation, mcp_tools)
        cli.run()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
