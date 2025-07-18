#!/usr/bin/env python3
"""
AWS Operations Agent Configuration Manager
Single source of truth for all project configuration
Replaces .env file with centralized JSON configuration
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

class BedrockAgentCoreConfigManager:
    """Manages AWS Operations Agent Gateway configuration from centralized JSON file"""
    
    def __init__(self, config_file: str = None):
        """Initialize configuration manager"""
        if config_file:
            self.config_file = Path(config_file)
        else:
            # Default to bedrock-agentcore-config.json in same directory as this script
            self.config_file = Path(__file__).parent / "bedrock-agentcore-config.json"
        
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {str(e)}")
    
    def validate_config(self) -> bool:
        """Validate that required configuration sections exist"""
        required_sections = ['aws', 'bedrock_agentcore', 'okta', 'environments', 'tool_schemas']
        
        for section in required_sections:
            if section not in self.config:
                print(f"❌ Missing required configuration section: {section}")
                return False
        
        # Validate active endpoint type is available
        active_endpoint = self.config['bedrock_agentcore'].get('active_endpoint', 'beta_endpoints')
        if active_endpoint not in self.config['bedrock_agentcore']:
            available_keys = [k for k in self.config['bedrock_agentcore'].keys() if k.endswith('_endpoints')]
            print(f"❌ Invalid active endpoint '{active_endpoint}'. Available endpoint keys: {', '.join(available_keys)}")
            return False
        
        # Validate environments have required fields
        for env_name, env_config in self.config['environments'].items():
            required_env_fields = ['aws_profile', 'aws_region', 'aws_account']
            for field in required_env_fields:
                if field not in env_config:
                    print(f"❌ Missing required field '{field}' in environment '{env_name}'")
                    return False
        
        return True
    
    # Project Configuration
    def get_project_name(self) -> str:
        """Get project name"""
        return self.config.get('project', {}).get('name', 'lambda-adaptor-bedrock-agentcore')
    
    def get_default_environment(self) -> str:
        """Get default environment"""
        return self.config.get('project', {}).get('default_environment', 'dev')
    
    # AWS Configuration
    def get_aws_config(self, environment: str = 'dev') -> Dict[str, str]:
        """Get AWS configuration for specified environment"""
        env_config = self.config['environments'].get(environment, {})
        
        return {
            'profile': env_config.get('aws_profile', self.config['aws']['default_profile']),
            'region': env_config.get('aws_region', self.config['aws']['default_region']),
            'account': env_config.get('aws_account', self.config['aws']['default_account'])
        }
    
    def get_lambda_role_arn(self, environment: str = 'dev') -> str:
        """Get Lambda execution role ARN for environment"""
        env_config = self.config['environments'].get(environment, {})
        return env_config.get('lambda_role_arn', f"arn:aws:iam::{self.get_aws_config(environment)['account']}:role/lambda-execution-role")
    
    # Bedrock AgentCore Configuration
    def get_bedrock_agentcore_endpoints(self, endpoint_override: str = None) -> Dict[str, str]:
        """Get Bedrock AgentCore API endpoints based on active_endpoint setting or override"""
        # Use override if provided, otherwise use active_endpoint from config
        endpoint_key = endpoint_override or self.config['bedrock_agentcore'].get('active_endpoint', 'beta_endpoints')
        
        # Return the endpoints for the specified key, fallback to beta_endpoints if not found
        return self.config['bedrock_agentcore'].get(endpoint_key, self.config['bedrock_agentcore'].get('beta_endpoints', {}))
    
    def get_active_endpoint_type(self) -> str:
        """Get the currently active endpoint type (clean name without '_endpoints')"""
        active_endpoint = self.config['bedrock_agentcore'].get('active_endpoint', 'beta_endpoints')
        # Remove '_endpoints' suffix for display purposes
        return active_endpoint.replace('_endpoints', '') if active_endpoint.endswith('_endpoints') else active_endpoint
    
    def get_available_endpoint_types(self) -> List[str]:
        """Get all available endpoint types from configuration (clean names without '_endpoints')"""
        endpoint_types = []
        for key in self.config['bedrock_agentcore'].keys():
            if key.endswith('_endpoints'):
                endpoint_type = key.replace('_endpoints', '')
                endpoint_types.append(endpoint_type)
        return sorted(endpoint_types)
    
    def is_valid_endpoint_type(self, endpoint_type: str) -> bool:
        """Check if the given endpoint type is valid/available"""
        # Handle both clean names (beta) and full keys (beta_endpoints)
        if endpoint_type.endswith('_endpoints'):
            return endpoint_type in self.config['bedrock_agentcore']
        else:
            return f"{endpoint_type}_endpoints" in self.config['bedrock_agentcore']
    
    def get_bedrock_agentcore_service_name(self) -> str:
        """Get Bedrock AgentCore service name"""
        return self.config['bedrock_agentcore'].get('service_name', 'bedrock-agentcore-control')
    
    def get_bedrock_agentcore_role_arn(self, environment: str = 'dev') -> str:
        """Get Bedrock AgentCore Gateway role ARN for environment"""
        env_config = self.config['environments'].get(environment, {})
        aws_config = self.get_aws_config(environment)
        role_name = env_config.get('bedrock_agentcore_role_name', f"{environment}-bedrock-agentcore-gateway-role")
        return f"arn:aws:iam::{aws_config['account']}:role/{role_name}"
    
    def get_mcp_endpoint_url(self, gateway_id: str = None, endpoint_override: str = None) -> str:
        """Get MCP endpoint URL from the active endpoint configuration"""
        endpoints = self.get_bedrock_agentcore_endpoints(endpoint_override)
        return endpoints.get('gateway_url', '')
    
    def get_mcp_gateway_url(self, gateway_id: str = None, endpoint_override: str = None) -> str:
        """Get MCP gateway URL from the active endpoint configuration"""
        return self.get_mcp_endpoint_url(gateway_id, endpoint_override)
    
    def update_gateway_info_from_response(self, gateway_response: dict) -> bool:
        """
        Update the active endpoint with gateway information from create_gateway response
        
        Args:
            gateway_response: The response from create_gateway API call
            
        Returns:
            bool: True if config was updated successfully
        """
        try:
            gateway_id = gateway_response.get('gatewayId')
            gateway_url = gateway_response.get('gatewayUrl')
            
            if not gateway_id or not gateway_url:
                print("❌ Missing gatewayId or gatewayUrl in response")
                return False
            
            # Get the active endpoint type
            active_endpoint = self.config['bedrock_agentcore'].get('active_endpoint', 'production_endpoints')
            
            # Update the config
            if active_endpoint in self.config['bedrock_agentcore']:
                old_gateway_id = self.config['bedrock_agentcore'][active_endpoint].get('gateway_id', 'Not set')
                old_gateway_url = self.config['bedrock_agentcore'][active_endpoint].get('gateway_url', 'Not set')
                
                self.config['bedrock_agentcore'][active_endpoint]['gateway_id'] = gateway_id
                self.config['bedrock_agentcore'][active_endpoint]['gateway_url'] = gateway_url
                
                # Save the updated config back to file
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                
                print(f"\n📝 Config Updated:")
                print(f"   Active Endpoint: {active_endpoint}")
                print(f"   Old Gateway ID: {old_gateway_id}")
                print(f"   New Gateway ID: {gateway_id}")
                print(f"   Old Gateway URL: {old_gateway_url}")
                print(f"   New Gateway URL: {gateway_url}")
                
                return True
            else:
                print(f"❌ Active endpoint '{active_endpoint}' not found in config")
                return False
                
        except Exception as e:
            print(f"❌ Failed to update config: {str(e)}")
            return False
    
    def clear_gateway_info(self, gateway_id: str = None) -> bool:
        """
        Clear gateway information from the active endpoint configuration
        Called when a gateway is deleted
        
        Args:
            gateway_id: Optional gateway ID to verify we're clearing the right gateway
            
        Returns:
            bool: True if config was updated successfully
        """
        try:
            # Get the active endpoint type
            active_endpoint = self.config['bedrock_agentcore'].get('active_endpoint', 'production_endpoints')
            
            # Update the config
            if active_endpoint in self.config['bedrock_agentcore']:
                current_gateway_id = self.config['bedrock_agentcore'][active_endpoint].get('gateway_id', 'Not set')
                current_gateway_url = self.config['bedrock_agentcore'][active_endpoint].get('gateway_url', 'Not set')
                
                # If gateway_id is provided, verify it matches before clearing
                if gateway_id and current_gateway_id != gateway_id:
                    print(f"⚠️  Gateway ID mismatch: config has '{current_gateway_id}', trying to clear '{gateway_id}'")
                    print("   Clearing anyway...")
                
                # Remove gateway info from config
                if 'gateway_id' in self.config['bedrock_agentcore'][active_endpoint]:
                    del self.config['bedrock_agentcore'][active_endpoint]['gateway_id']
                if 'gateway_url' in self.config['bedrock_agentcore'][active_endpoint]:
                    del self.config['bedrock_agentcore'][active_endpoint]['gateway_url']
                
                # Save the updated config back to file
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                
                print(f"\n📝 Config Cleared:")
                print(f"   Active Endpoint: {active_endpoint}")
                print(f"   Cleared Gateway ID: {current_gateway_id}")
                print(f"   Cleared Gateway URL: {current_gateway_url}")
                
                return True
            else:
                print(f"❌ Active endpoint '{active_endpoint}' not found in config")
                return False
                
        except Exception as e:
            print(f"❌ Failed to clear config: {str(e)}")
            return False
    
    # Okta Configuration
    def get_okta_config(self) -> Dict[str, str]:
        """Get Okta configuration"""
        return self.config['okta']
    
    def get_okta_discovery_url(self) -> str:
        """Get Okta OIDC discovery URL"""
        return self.config['okta']['discovery_url']
    
    def get_okta_audience(self) -> str:
        """Get Okta audience"""
        return self.config['okta']['audience']
    
    def get_okta_authorizer_config(self) -> Dict[str, Any]:
        """Get Okta authorizer configuration for Bedrock AgentCore Gateway"""
        okta_config = self.get_okta_config()
        return {
            "customJWTAuthorizer": {
                "allowedAudience": [okta_config.get('audience', 'api://default')],
                "discoveryUrl": okta_config.get('discovery_url', '')
            }
        }
    
    # Bedrock Configuration
    def get_bedrock_config(self) -> Dict[str, str]:
        """Get Bedrock configuration"""
        return self.config.get('bedrock', {
            'model_id': 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
            'region': 'us-west-2'
        })
    
    def get_bedrock_model_id(self) -> str:
        """Get Bedrock model ID"""
        return self.get_bedrock_config()['model_id']
    
    def get_bedrock_region(self) -> str:
        """Get Bedrock region"""
        return self.get_bedrock_config()['region']
    
    # Lambda Configuration
    def get_lambda_arn(self, environment: str = 'dev', function_name: str = None) -> str:
        """Get Lambda function ARN from config or generate it"""
        env_config = self.config['environments'].get(environment, {})
        
        # First try to get from config
        if 'lambda_arn' in env_config:
            return env_config['lambda_arn']
        
        # Fallback to generating ARN if not in config
        aws_config = self.get_aws_config(environment)
        if not function_name:
            # Use default naming convention
            function_name = f"{environment}-bedrock-agentcore-hello-world"
        
        return f"arn:aws:lambda:{aws_config['region']}:{aws_config['account']}:function:{function_name}"
    
    def get_lambda_target_config(self, lambda_arn: str) -> Dict[str, Any]:
        """Get Lambda target configuration with tool schemas"""
        return {
            'mcp': {
                'lambda': {
                    'lambdaArn': lambda_arn,
                    'toolSchema': {
                        'inlinePayload': self.get_tool_schemas()
                    }
                }
            }
        }
    
    def get_credential_provider_config(self) -> List[Dict[str, str]]:
        """Get credential provider configuration"""
        return [{'credentialProviderType': 'GATEWAY_IAM_ROLE'}]
    
    # Tool Schemas
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas"""
        return self.config.get('tool_schemas', [])
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get specific tool schema by name"""
        for tool in self.get_tool_schemas():
            if tool.get('name') == tool_name:
                return tool
        return None
    
    def get_tool_count(self) -> int:
        """Get total number of tools"""
        return len(self.get_tool_schemas())
    
    def get_tool_names(self) -> List[str]:
        """Get list of all tool names"""
        return [tool.get('name', 'unknown') for tool in self.get_tool_schemas()]
    
    # Environment Management
    def get_environments(self) -> List[str]:
        """Get list of available environments"""
        return list(self.config.get('environments', {}).keys())
    
    def get_environment_config(self, environment: str) -> Dict[str, Any]:
        """Get full configuration for specific environment"""
        return self.config['environments'].get(environment, {})
    
    # Utility Methods
    def get_gateway_description(self, environment: str = 'dev') -> str:
        """Generate gateway description"""
        tool_count = self.get_tool_count()
        project_name = self.get_project_name()
        return f"{project_name.title()} Gateway for {environment} environment - {tool_count} tools available"
    
    def get_target_description(self, environment: str = 'dev') -> str:
        """Generate target description"""
        tool_count = self.get_tool_count()
        tool_names = ', '.join(self.get_tool_names())
        return f"Lambda Target for {environment} environment - {tool_count} tools: {tool_names}"
    
    def print_config_summary(self, environment: str = 'dev'):
        """Print configuration summary"""
        print(f"\n📋 Configuration Summary")
        print("=" * 50)
        print(f"Project: {self.get_project_name()}")
        print(f"Environment: {environment}")
        print(f"AWS Profile: {self.get_aws_config(environment)['profile']}")
        print(f"AWS Region: {self.get_aws_config(environment)['region']}")
        print(f"AWS Account: {self.get_aws_config(environment)['account']}")
        available_endpoints = ', '.join(self.get_available_endpoint_types())
        print(f"Bedrock AgentCore Endpoint: {self.get_bedrock_agentcore_endpoints()['control_plane']} (active: {self.get_active_endpoint_type()})")
        print(f"Available Endpoints: {available_endpoints}")
        print(f"Bedrock AgentCore Role: {self.get_bedrock_agentcore_role_arn(environment)}")
        print(f"Lambda Role: {self.get_lambda_role_arn(environment)}")
        print(f"Okta Domain: {self.get_okta_config()['domain']}")
        print(f"Tools Available: {self.get_tool_count()}")
        print(f"Tool Names: {', '.join(self.get_tool_names())}")
    
    # Legacy .env compatibility methods (for migration)
    def get_env_equivalent(self, env_var: str, environment: str = 'dev') -> Optional[str]:
        """Get configuration value equivalent to .env variable (for migration)"""
        env_mapping = {
            'AWS_REGION': lambda: self.get_aws_config(environment)['region'],
            'AWS_ACCOUNT_ID': lambda: self.get_aws_config(environment)['account'],
            'LAMBDA_ROLE_ARN': lambda: self.get_lambda_role_arn(environment),
            'OKTA_DOMAIN': lambda: self.get_okta_config()['domain'],
            'OKTA_CLIENT_ID': lambda: self.get_okta_config()['client_id'],
            'OKTA_REDIRECT_URI': lambda: self.get_okta_config().get('redirect_uri'),
            'OKTA_AUDIENCE': lambda: self.get_okta_config()['audience'],
            'BEDROCK_MODEL_ID': lambda: self.get_bedrock_model_id(),
            'BEDROCK_REGION': lambda: self.get_bedrock_region(),
            'BEDROCK_AGENTCORE_ENDPOINT': lambda: self.get_bedrock_agentcore_endpoints().get('legacy_endpoint'),
            'BEDROCK_AGENTCORE_SERVICE_NAME': lambda: self.get_bedrock_agentcore_service_name(),
            'PROJECT_NAME': lambda: self.get_project_name(),
            'ENVIRONMENT': lambda: environment
        }
        
        if env_var in env_mapping:
            try:
                return env_mapping[env_var]()
            except (KeyError, TypeError):
                return None
        return None
    
    def validate_required_settings(self, environment: str = 'dev') -> List[str]:
        """Validate required settings and return list of missing ones"""
        missing = []
        
        # Check Okta configuration
        okta_config = self.get_okta_config()
        if not okta_config.get('domain'):
            missing.append('okta.domain')
        if not okta_config.get('client_id'):
            missing.append('okta.client_id')
        
        # Check AWS configuration
        aws_config = self.get_aws_config(environment)
        if not aws_config.get('account'):
            missing.append(f'environments.{environment}.aws_account')
        
        # Check Lambda role
        try:
            self.get_lambda_role_arn(environment)
        except:
            missing.append(f'environments.{environment}.lambda_role_arn')
        
        return missing


# Convenience function for easy import
def get_config_manager(config_file: str = None) -> BedrockAgentCoreConfigManager:
    """Get configuration manager instance"""
    return BedrockAgentCoreConfigManager(config_file)


# For backward compatibility
def get_config(environment: str = "dev", config_file: str = None) -> Dict[str, Any]:
    """Get configuration for environment"""
    manager = get_config_manager(config_file)
    return {
        'environment': environment,
        'aws': manager.get_aws_config(environment),
        'bedrock_agentcore': manager.get_bedrock_agentcore_endpoints(),
        'okta': manager.get_okta_config(),
        'tool_schemas': manager.get_tool_schemas()
    }


if __name__ == "__main__":
    # Test configuration manager
    manager = BedrockAgentCoreConfigManager()
    
    print("🧪 Testing Bedrock AgentCore Configuration Manager")
    print("=" * 50)
    
    # Validate configuration
    manager.validate_config()
    
    # Print summary
    manager.print_config_summary("dev")
    
    # Test .env compatibility
    print(f"\n🔄 Testing .env compatibility:")
    print(f"AWS_REGION: {manager.get_env_equivalent('AWS_REGION', 'dev')}")
    print(f"OKTA_DOMAIN: {manager.get_env_equivalent('OKTA_DOMAIN', 'dev')}")
    print(f"PROJECT_NAME: {manager.get_env_equivalent('PROJECT_NAME', 'dev')}")
    
    print("\n✅ Configuration Manager Test Complete")
