#!/usr/bin/env python
"""
Deploy Property Search and Booking Agents with OAuth Authentication
Uses AgentCore SDK for deployment with Cognito JWT authorizer
"""

import os
import sys
import json
import subprocess
import time

class AgentDeployer:
    def __init__(self, config_file='cognito_config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.agents = [
            {
                'name': 'property_search_agent',
                'path': 'propertysearchagent_strands',
                'entrypoint': 'agent_agentcore.py',
                'description': 'Property Search Agent with OAuth authentication'
            },
            {
                'name': 'property_booking_agent',
                'path': 'propertybookingagent_strands',
                'entrypoint': 'agent_agentcore.py',
                'description': 'Property Booking Agent with OAuth authentication'
            },
            {
                'name': 'realestate_coordinator',
                'path': 'realestate_coordinator',
                'entrypoint': 'agent_agentcore.py',
                'description': 'Real Estate Coordinator Agent - Orchestrates sub-agents with A2A protocol'
            }
        ]
    
    def load_config(self):
        """Load Cognito configuration."""
        if not os.path.exists(self.config_file):
            print(f"✗ Error: {self.config_file} not found")
            print("Please run: python setup_cognito_automated.py")
            sys.exit(1)
        
        with open(self.config_file, 'r') as f:
            config = json.load(f)
        
        print(f"✓ Loaded configuration from {self.config_file}")
        return config
    
    def check_agent_directory(self, agent_path):
        """Check if agent directory exists and has required files."""
        # Get the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, agent_path)
        
        if not os.path.exists(full_path):
            print(f"✗ Error: Agent directory not found: {full_path}")
            return False
        
        agent_path = full_path  # Update to use full path
        
        required_files = ['agent_agentcore.py', 'requirements.txt']
        for file in required_files:
            file_path = os.path.join(agent_path, file)
            if not os.path.exists(file_path):
                print(f"✗ Error: Required file not found: {file_path}")
                return False
        
        return True
    
    def configure_agent(self, agent):
        """Configure agent with OAuth settings using agentcore configure."""
        print(f"\n{'='*70}")
        print(f"Configuring {agent['name']}")
        print(f"{'='*70}")
        
        # Get the script directory and construct full path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        agent_path = os.path.join(script_dir, agent['path'])
        
        if not os.path.exists(agent_path):
            print(f"✗ Error: Agent directory not found: {agent_path}")
            return False
        
        if not self.check_agent_directory(agent['path']):
            return False
        
        # Change to agent directory
        original_dir = os.getcwd()
        os.chdir(agent_path)
        
        try:
            # Check if already configured
            config_file = '.bedrock_agentcore.yaml'
            if os.path.exists(config_file):
                print(f"✓ Agent already configured: {config_file}")
                
                # Update OAuth configuration in existing config
                self.update_agent_config(config_file)
                os.chdir(original_dir)
                return True
            
            # Run agentcore configure
            print("Running agentcore configure...")
            
            # Don't log the full command for security
            print(f"Command: agentcore configure -e {agent['entrypoint']} --protocol A2A")
            
            # Note: This is interactive, so we'll create the config manually
            print("⚠️  Creating configuration manually...")
            self.create_agent_config(agent)
            
            os.chdir(original_dir)
            return True
            
        except Exception as e:
            print(f"✗ Error configuring agent: {e}")
            os.chdir(original_dir)
            return False
    
    def get_aws_account_id(self):
        """Get AWS account ID from STS."""
        try:
            import boto3
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            return identity['Account']
        except Exception as e:
            print(f"✗ Error getting AWS account ID: {e}")
            print("Please ensure AWS credentials are configured")
            sys.exit(1)
    
    def create_agent_config(self, agent):
        """Create agent configuration file with OAuth settings."""
        config_file = '.bedrock_agentcore.yaml'
        
        # Get AWS account ID
        account_id = self.get_aws_account_id()
        print(f"✓ Using AWS Account: {account_id}")
        
        # Ensure discovery URL has the full path
        discovery_url = self.config['discovery_url']
        if not discovery_url.endswith('/.well-known/openid-configuration'):
            discovery_url = discovery_url.rstrip('/') + '/.well-known/openid-configuration'
        
        config = {
            'default_agent': agent['name'],
            'agents': {
                agent['name']: {
                    'name': agent['name'],
                    'entrypoint': os.path.abspath(agent['entrypoint']),
                    'deployment_type': 'container',
                    'runtime_type': None,
                    'platform': 'linux/arm64',
                    'container_runtime': 'docker',
                    'source_path': None,
                    'aws': {
                        'account': account_id,
                        'execution_role_auto_create': True,
                        'region': self.config['region'],
                        'ecr_auto_create': True,
                        'network_configuration': {
                            'network_mode': 'PUBLIC'
                        },
                        'protocol_configuration': {
                            'server_protocol': 'A2A'
                        },
                        'observability': {
                            'enabled': True
                        }
                    },
                    'authorizer_configuration': {
                        'customJWTAuthorizer': {
                            'allowedClients': [self.config['client_id']],
                            'discoveryUrl': discovery_url
                        }
                    },
                    'requestHeaderConfiguration': {
                        'requestHeaderAllowlist': ['Authorization']
                    },
                    'memory': {
                        'mode': 'STM_ONLY'
                    }
                }
            }
        }
        
        # Write YAML config
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"✓ Created configuration: {config_file}")
        print(f"  OAuth Client ID: {self.config['client_id']}")
        print(f"  Discovery URL: {self.config['discovery_url']}")
        print("  Request Header Allowlist: Authorization")
    
    def update_agent_config(self, config_file):
        """Update existing agent configuration with OAuth settings."""
        import yaml
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Get AWS account ID
        account_id = self.get_aws_account_id()
        print(f"✓ Using AWS Account: {account_id}")
        
        # Ensure discovery URL has the full path
        discovery_url = self.config['discovery_url']
        if not discovery_url.endswith('/.well-known/openid-configuration'):
            discovery_url = discovery_url.rstrip('/') + '/.well-known/openid-configuration'
        
        # Update authorizer configuration
        for agent_name, agent_config in config.get('agents', {}).items():
            agent_config['authorizer_configuration'] = {
                'customJWTAuthorizer': {
                    'allowedClients': [self.config['client_id']],
                    'discoveryUrl': discovery_url
                }
            }
            
            # Add request header configuration to allow Authorization header
            agent_config['requestHeaderConfiguration'] = {
                'requestHeaderAllowlist': ['Authorization']
            }
            
            # Ensure protocol is A2A
            if 'aws' not in agent_config:
                agent_config['aws'] = {}
            
            # Add account ID if missing
            if 'account' not in agent_config['aws']:
                agent_config['aws']['account'] = account_id
                print("✓ Added AWS account ID to configuration")
            
            if 'protocol_configuration' not in agent_config['aws']:
                agent_config['aws']['protocol_configuration'] = {}
            agent_config['aws']['protocol_configuration']['server_protocol'] = 'A2A'
            
            # Enable short-term memory for conversation context
            agent_config['memory'] = {
                'mode': 'STM_ONLY'
            }
        
        # Write updated config
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"✓ Updated OAuth configuration in {config_file}")
        print("  Request Header Allowlist: Authorization")
    
    def deploy_agent(self, agent, env_vars=None):
        """Deploy agent using agentcore launch.
        
        Args:
            agent: Agent configuration dict
            env_vars: Optional dict of environment variables to pass to the agent
        """
        print(f"\n{'='*70}")
        print(f"Deploying {agent['name']}")
        print(f"{'='*70}")
        
        # Get the script directory and construct full path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        agent_path = os.path.join(script_dir, agent['path'])
        
        original_dir = os.getcwd()
        os.chdir(agent_path)
        
        try:
            # Use agentcore CLI - command is hardcoded and safe
            print("Running agentcore launch...")
            
            # Build command with explicit validation
            # Base command is hardcoded - no user input
            base_cmd = ['agentcore', 'launch', '--auto-update-on-conflict']
            
            # Validate and add environment variables if provided
            env_args = []
            if env_vars:
                for key, value in env_vars.items():
                    # Validate key is alphanumeric with underscores (safe)
                    if not key.replace('_', '').isalnum():
                        raise ValueError(f"Invalid environment variable name: {key}")
                    
                    # Add to command
                    env_args.extend(['--env', f'{key}={value}'])
            
            # Combine validated command parts
            cmd = base_cmd + env_args
            
            print("\nCommand: agentcore launch --auto-update-on-conflict [+ env vars]")
            
            # Execute with validated command
            # Security: All command components are validated and from trusted sources
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                check=False  # Don't raise exception on non-zero exit
            )
            
            print(result.stdout)
            
            if result.returncode != 0:
                print("✗ Deployment failed:")
                print(result.stderr)
                os.chdir(original_dir)
                return False
            
            print(f"✓ Successfully deployed {agent['name']}")
            
            # Extract agent ARN from output
            agent_arn = self.extract_agent_arn(result.stdout)
            if agent_arn:
                print(f"  Agent ARN: {agent_arn}")
                agent['arn'] = agent_arn
            
            os.chdir(original_dir)
            return True
            
        except subprocess.TimeoutExpired:
            print("✗ Deployment timed out after 10 minutes")
            os.chdir(original_dir)
            return False
        except Exception as e:
            print(f"✗ Error deploying agent: {e}")
            os.chdir(original_dir)
            return False
    
    def extract_agent_arn(self, output):
        """Extract agent ARN from deployment output."""
        import re
        import yaml
        
        # First try: read from .bedrock_agentcore.yaml (most reliable)
        config_file = '.bedrock_agentcore.yaml'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                for agent_name, agent_config in config.get('agents', {}).items():
                    # Check nested bedrock_agentcore section
                    bc = agent_config.get('bedrock_agentcore', {})
                    if bc and bc.get('agent_arn'):
                        return bc['agent_arn']
            except Exception:
                pass
        
        # Fallback: parse from CLI output
        arn_pattern = r'arn:aws:bedrock-agentcore:[a-z0-9-]+:\d+:runtime/[a-zA-Z0-9_-]+'
        matches = re.findall(arn_pattern, output)
        
        if matches:
            # Return the first match (should be the agent ARN)
            return matches[0]
        
        # Fallback: try to find in "Agent ARN:" line
        arn_line_pattern = r'Agent ARN:\s*(arn:aws:bedrock-agentcore:[^\s]+)'
        line_matches = re.findall(arn_line_pattern, output, re.MULTILINE)
        if line_matches:
            return line_matches[0]
        
        return None
    
    def arn_to_runtime_url(self, arn):
        """Convert agent ARN to runtime invocation URL."""
        # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-name
        # URL format: https://bedrock-agentcore.region.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aregion%3Aaccount%3Aruntime%2Fruntime-name/invocations
        
        import urllib.parse
        
        # Extract region from ARN
        parts = arn.split(':')
        region = parts[3]
        
        # URL encode the ARN
        encoded_arn = urllib.parse.quote(arn, safe='')
        
        # Construct runtime URL
        runtime_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations"
        
        return runtime_url
    

    
    def save_deployment_info(self, deployed_agents):
        """Save deployment information."""
        # Add runtime URLs to agents that have ARNs
        for agent in deployed_agents:
            if 'arn' in agent and 'runtime_url' not in agent:
                agent['runtime_url'] = self.arn_to_runtime_url(agent['arn'])
        
        deployment_info = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'cognito_config': {
                'user_pool_id': self.config['user_pool_id'],
                'client_id': self.config['client_id'],
                'discovery_url': self.config['discovery_url']
            },
            'agents': deployed_agents
        }
        
        output_file = 'deployment_info.json'
        with open(output_file, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"\n✓ Deployment information saved to: {output_file}")
    
    def deploy_all(self):
        """Deploy all agents with OAuth authentication."""
        print("\n" + "="*70)
        print("DEPLOYING AGENTS WITH OAUTH AUTHENTICATION")
        print("="*70)
        print(f"Cognito User Pool: {self.config['user_pool_id']}")
        print(f"Client ID: {self.config['client_id']}")
        print(f"Region: {self.config['region']}")
        
        deployed_agents = []
        failed_agents = []
        
        # Separate coordinator from sub-agents
        sub_agents = [a for a in self.agents if a['name'] != 'realestate_coordinator']
        coordinator = next((a for a in self.agents if a['name'] == 'realestate_coordinator'), None)
        
        # Deploy sub-agents first
        print("\n" + "="*70)
        print("PHASE 1: DEPLOYING SUB-AGENTS")
        print("="*70)
        
        for agent in sub_agents:
            print(f"\n{'='*70}")
            print(f"Processing: {agent['name']}")
            print(f"{'='*70}")
            
            # Configure agent
            if not self.configure_agent(agent):
                print(f"✗ Failed to configure {agent['name']}")
                failed_agents.append(agent['name'])
                continue
            
            # Deploy agent
            if not self.deploy_agent(agent):
                print(f"✗ Failed to deploy {agent['name']}")
                failed_agents.append(agent['name'])
                continue
            
            deployed_agents.append(agent)
        
        # Configure and deploy coordinator with sub-agent URLs
        if coordinator and len(deployed_agents) == len(sub_agents):
            print("\n" + "="*70)
            print("PHASE 2: DEPLOYING COORDINATOR")
            print("="*70)
            
            # Get sub-agent URLs
            search_agent = next((a for a in deployed_agents if 'search' in a['name']), None)
            booking_agent = next((a for a in deployed_agents if 'booking' in a['name']), None)
            
            if search_agent and booking_agent and 'arn' in search_agent and 'arn' in booking_agent:
                search_url = self.arn_to_runtime_url(search_agent['arn'])
                booking_url = self.arn_to_runtime_url(booking_agent['arn'])
                
                # Store URLs in agent info
                search_agent['runtime_url'] = search_url
                booking_agent['runtime_url'] = booking_url
                
                print(f"\n✓ Sub-agent URLs:")
                print(f"  Search: {search_url}")
                print(f"  Booking: {booking_url}")
                
                # Configure coordinator
                if self.configure_agent(coordinator):
                    # Deploy coordinator with environment variables including Cognito credentials
                    # Coordinator will use these to generate bearer tokens for sub-agent authentication
                    print(f"\n✓ Configuring coordinator with Cognito credentials for token generation...")
                    coordinator_env = {
                        'PROPERTY_SEARCH_AGENT_URL': search_url,
                        'PROPERTY_BOOKING_AGENT_URL': booking_url,
                        'COGNITO_TOKEN_ENDPOINT': self.config['oauth_token_url'],
                        'COGNITO_CLIENT_ID': self.config['client_id'],
                        'COGNITO_CLIENT_SECRET': self.config['client_secret']
                    }
                    
                    if self.deploy_agent(coordinator, env_vars=coordinator_env):
                        deployed_agents.append(coordinator)
                    else:
                        print(f"✗ Failed to deploy coordinator")
                        failed_agents.append(coordinator['name'])
                else:
                    print(f"✗ Failed to configure coordinator")
                    failed_agents.append(coordinator['name'])
            else:
                print(f"✗ Cannot deploy coordinator: sub-agents not fully deployed")
                failed_agents.append(coordinator['name'])
        elif coordinator:
            print(f"\n✗ Skipping coordinator deployment: sub-agents failed")
            failed_agents.append(coordinator['name'])
        
        # Print summary
        print("\n" + "="*70)
        print("DEPLOYMENT SUMMARY")
        print("="*70)
        
        if deployed_agents:
            print(f"\n✅ Successfully deployed {len(deployed_agents)} agent(s):")
            for agent in deployed_agents:
                print(f"  • {agent['name']}")
                if 'arn' in agent:
                    print(f"    ARN: {agent['arn']}")
        
        if failed_agents:
            print(f"\n✗ Failed to deploy {len(failed_agents)} agent(s):")
            for name in failed_agents:
                print(f"  • {name}")
        
        # Save deployment info
        if deployed_agents:
            self.save_deployment_info(deployed_agents)
        
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\n1. Get bearer token:")
        print("   python get_bearer_token.py")
        print("\n2. Test agents:")
        print("   python test_a2a_with_oauth.py")
        
        return len(failed_agents) == 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy agents with OAuth authentication')
    parser.add_argument('--config', default='cognito_config.json', help='Cognito config file')
    args = parser.parse_args()
    
    # Check if PyYAML is installed
    try:
        import yaml
    except ImportError:
        print("✗ Error: PyYAML not installed")
        print("Install with: pip install pyyaml")
        sys.exit(1)
    
    deployer = AgentDeployer(config_file=args.config)
    success = deployer.deploy_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
