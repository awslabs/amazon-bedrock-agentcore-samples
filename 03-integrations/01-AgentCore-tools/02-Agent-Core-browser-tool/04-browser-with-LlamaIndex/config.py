"""
Configuration management for LlamaIndex-AgentCore browser tool integration.

This module handles AWS credentials, AgentCore endpoints, and browser session
configuration for the integration.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from interfaces import IConfigurationManager
from exceptions import ConfigurationError


@dataclass
class AWSCredentials:
    """AWS credentials configuration."""
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    region: str = "us-east-1"
    profile: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format."""
        result = {}
        if self.access_key_id:
            result["aws_access_key_id"] = self.access_key_id
        if self.secret_access_key:
            result["aws_secret_access_key"] = self.secret_access_key
        if self.session_token:
            result["aws_session_token"] = self.session_token
        if self.region:
            result["region_name"] = self.region
        return result


@dataclass
class AgentCoreEndpoints:
    """AgentCore service endpoints configuration."""
    browser_tool_endpoint: Optional[str] = None
    runtime_endpoint: Optional[str] = None
    memory_endpoint: Optional[str] = None
    identity_endpoint: Optional[str] = None
    gateway_endpoint: Optional[str] = None
    base_url: Optional[str] = None
    test_mode: bool = False  # Enable test mode when AgentCore service is not available
    
    def __post_init__(self):
        """Set default endpoints if base_url is provided."""
        if self.base_url and not self.browser_tool_endpoint:
            self.browser_tool_endpoint = f"{self.base_url}/browser-tool"
        if self.base_url and not self.runtime_endpoint:
            self.runtime_endpoint = f"{self.base_url}/runtime"


@dataclass
class BrowserConfiguration:
    """Browser session configuration parameters."""
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    timeout_seconds: int = 30
    page_load_timeout: int = 30
    element_timeout: int = 10
    enable_javascript: bool = True
    enable_images: bool = True
    enable_cookies: bool = True
    enable_local_storage: bool = True
    enable_session_storage: bool = True
    proxy_settings: Optional[Dict[str, str]] = None
    browser_args: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API calls."""
        return asdict(self)


@dataclass
class RetryConfiguration:
    """Retry behavior configuration."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout", "network_error", "rate_limited", "session_expired"
    ])


@dataclass
class LoggingConfiguration:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enable_debug: bool = False
    log_file: Optional[str] = None
    log_agentcore_requests: bool = True
    log_agentcore_responses: bool = False  # May contain sensitive data
    max_log_size_mb: int = 100


@dataclass
class IntegrationConfig:
    """Complete integration configuration."""
    aws_credentials: AWSCredentials = field(default_factory=AWSCredentials)
    agentcore_endpoints: AgentCoreEndpoints = field(default_factory=AgentCoreEndpoints)
    browser_config: BrowserConfiguration = field(default_factory=BrowserConfiguration)
    retry_config: RetryConfiguration = field(default_factory=RetryConfiguration)
    logging_config: LoggingConfiguration = field(default_factory=LoggingConfiguration)
    
    # LlamaIndex specific settings
    llm_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    vision_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    enable_multi_modal: bool = True
    
    # Security settings
    enable_input_sanitization: bool = True
    enable_pii_scrubbing: bool = True
    audit_logging: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)


class ConfigurationManager(IConfigurationManager):
    """Concrete implementation of configuration management."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self._config: Optional[IntegrationConfig] = None
        self._aws_session: Optional[boto3.Session] = None
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from file or environment variables.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationError: If configuration loading fails
        """
        try:
            # Start with default configuration
            config = IntegrationConfig()
            
            # Load from file if provided
            if config_path or self.config_path:
                file_path = Path(config_path or self.config_path)
                if file_path.exists():
                    config = self._load_from_file(file_path, config)
            
            # Override with environment variables
            config = self._load_from_environment(config)
            
            # Validate the final configuration
            self.validate_config(config.to_dict())
            
            self._config = config
            return config.to_dict()
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e
    
    def _load_from_file(self, file_path: Path, base_config: IntegrationConfig) -> IntegrationConfig:
        """Load configuration from file."""
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    file_config = yaml.safe_load(f)
                elif file_path.suffix.lower() == '.json':
                    file_config = json.load(f)
                else:
                    raise ConfigurationError(f"Unsupported config file format: {file_path.suffix}")
            
            # Merge file configuration with base configuration
            return self._merge_config(base_config, file_config)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load config from {file_path}: {str(e)}") from e
    
    def _load_from_environment(self, base_config: IntegrationConfig) -> IntegrationConfig:
        """Load configuration from environment variables."""
        # AWS credentials
        if os.getenv('AWS_ACCESS_KEY_ID'):
            base_config.aws_credentials.access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        if os.getenv('AWS_SECRET_ACCESS_KEY'):
            base_config.aws_credentials.secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        if os.getenv('AWS_SESSION_TOKEN'):
            base_config.aws_credentials.session_token = os.getenv('AWS_SESSION_TOKEN')
        if os.getenv('AWS_DEFAULT_REGION'):
            base_config.aws_credentials.region = os.getenv('AWS_DEFAULT_REGION')
        if os.getenv('AWS_PROFILE'):
            base_config.aws_credentials.profile = os.getenv('AWS_PROFILE')
        
        # AgentCore endpoints
        if os.getenv('AGENTCORE_BASE_URL'):
            base_config.agentcore_endpoints.base_url = os.getenv('AGENTCORE_BASE_URL')
        if os.getenv('AGENTCORE_BROWSER_TOOL_ENDPOINT'):
            base_config.agentcore_endpoints.browser_tool_endpoint = os.getenv('AGENTCORE_BROWSER_TOOL_ENDPOINT')
        
        # Browser configuration
        if os.getenv('BROWSER_HEADLESS'):
            base_config.browser_config.headless = os.getenv('BROWSER_HEADLESS').lower() == 'true'
        if os.getenv('BROWSER_VIEWPORT_WIDTH'):
            base_config.browser_config.viewport_width = int(os.getenv('BROWSER_VIEWPORT_WIDTH'))
        if os.getenv('BROWSER_VIEWPORT_HEIGHT'):
            base_config.browser_config.viewport_height = int(os.getenv('BROWSER_VIEWPORT_HEIGHT'))
        if os.getenv('BROWSER_TIMEOUT'):
            base_config.browser_config.timeout_seconds = int(os.getenv('BROWSER_TIMEOUT'))
        
        # LlamaIndex models
        if os.getenv('LLAMAINDEX_LLM_MODEL'):
            base_config.llm_model = os.getenv('LLAMAINDEX_LLM_MODEL')
        if os.getenv('LLAMAINDEX_VISION_MODEL'):
            base_config.vision_model = os.getenv('LLAMAINDEX_VISION_MODEL')
        
        return base_config
    
    def _merge_config(self, base_config: IntegrationConfig, file_config: Dict[str, Any]) -> IntegrationConfig:
        """Merge file configuration with base configuration."""
        # Create a new config starting from base
        merged_config = IntegrationConfig()
        
        # Copy base config values
        merged_config.aws_credentials = base_config.aws_credentials
        merged_config.agentcore_endpoints = base_config.agentcore_endpoints
        merged_config.browser_config = base_config.browser_config
        merged_config.retry_config = base_config.retry_config
        merged_config.logging_config = base_config.logging_config
        merged_config.llm_model = base_config.llm_model
        merged_config.vision_model = base_config.vision_model
        merged_config.enable_multi_modal = base_config.enable_multi_modal
        merged_config.enable_input_sanitization = base_config.enable_input_sanitization
        merged_config.enable_pii_scrubbing = base_config.enable_pii_scrubbing
        merged_config.audit_logging = base_config.audit_logging
        
        # Merge AWS credentials
        if 'aws_credentials' in file_config:
            aws_config = file_config['aws_credentials']
            if 'access_key_id' in aws_config:
                merged_config.aws_credentials.access_key_id = aws_config['access_key_id']
            if 'secret_access_key' in aws_config:
                merged_config.aws_credentials.secret_access_key = aws_config['secret_access_key']
            if 'session_token' in aws_config:
                merged_config.aws_credentials.session_token = aws_config['session_token']
            if 'region' in aws_config:
                merged_config.aws_credentials.region = aws_config['region']
            if 'profile' in aws_config:
                merged_config.aws_credentials.profile = aws_config['profile']
        
        # Merge AgentCore endpoints
        if 'agentcore_endpoints' in file_config:
            endpoints_config = file_config['agentcore_endpoints']
            if 'browser_tool_endpoint' in endpoints_config:
                merged_config.agentcore_endpoints.browser_tool_endpoint = endpoints_config['browser_tool_endpoint']
            if 'runtime_endpoint' in endpoints_config:
                merged_config.agentcore_endpoints.runtime_endpoint = endpoints_config['runtime_endpoint']
            if 'memory_endpoint' in endpoints_config:
                merged_config.agentcore_endpoints.memory_endpoint = endpoints_config['memory_endpoint']
            if 'identity_endpoint' in endpoints_config:
                merged_config.agentcore_endpoints.identity_endpoint = endpoints_config['identity_endpoint']
            if 'gateway_endpoint' in endpoints_config:
                merged_config.agentcore_endpoints.gateway_endpoint = endpoints_config['gateway_endpoint']
            if 'base_url' in endpoints_config:
                merged_config.agentcore_endpoints.base_url = endpoints_config['base_url']
            if 'test_mode' in endpoints_config:
                merged_config.agentcore_endpoints.test_mode = endpoints_config['test_mode']
        
        # Merge browser configuration
        if 'browser_config' in file_config:
            browser_config = file_config['browser_config']
            if 'headless' in browser_config:
                merged_config.browser_config.headless = browser_config['headless']
            if 'viewport_width' in browser_config:
                merged_config.browser_config.viewport_width = browser_config['viewport_width']
            if 'viewport_height' in browser_config:
                merged_config.browser_config.viewport_height = browser_config['viewport_height']
            if 'user_agent' in browser_config:
                merged_config.browser_config.user_agent = browser_config['user_agent']
            if 'timeout_seconds' in browser_config:
                merged_config.browser_config.timeout_seconds = browser_config['timeout_seconds']
            if 'page_load_timeout' in browser_config:
                merged_config.browser_config.page_load_timeout = browser_config['page_load_timeout']
            if 'element_timeout' in browser_config:
                merged_config.browser_config.element_timeout = browser_config['element_timeout']
            if 'enable_javascript' in browser_config:
                merged_config.browser_config.enable_javascript = browser_config['enable_javascript']
            if 'enable_images' in browser_config:
                merged_config.browser_config.enable_images = browser_config['enable_images']
            if 'enable_cookies' in browser_config:
                merged_config.browser_config.enable_cookies = browser_config['enable_cookies']
            if 'enable_local_storage' in browser_config:
                merged_config.browser_config.enable_local_storage = browser_config['enable_local_storage']
            if 'enable_session_storage' in browser_config:
                merged_config.browser_config.enable_session_storage = browser_config['enable_session_storage']
            if 'proxy_settings' in browser_config:
                merged_config.browser_config.proxy_settings = browser_config['proxy_settings']
            if 'browser_args' in browser_config:
                merged_config.browser_config.browser_args = browser_config['browser_args']
        
        # Merge retry configuration
        if 'retry_config' in file_config:
            retry_config = file_config['retry_config']
            if 'max_attempts' in retry_config:
                merged_config.retry_config.max_attempts = retry_config['max_attempts']
            if 'base_delay' in retry_config:
                merged_config.retry_config.base_delay = retry_config['base_delay']
            if 'max_delay' in retry_config:
                merged_config.retry_config.max_delay = retry_config['max_delay']
            if 'exponential_base' in retry_config:
                merged_config.retry_config.exponential_base = retry_config['exponential_base']
            if 'jitter' in retry_config:
                merged_config.retry_config.jitter = retry_config['jitter']
            if 'retryable_errors' in retry_config:
                merged_config.retry_config.retryable_errors = retry_config['retryable_errors']
        
        # Merge top-level configuration
        if 'llm_model' in file_config:
            merged_config.llm_model = file_config['llm_model']
        if 'vision_model' in file_config:
            merged_config.vision_model = file_config['vision_model']
        if 'enable_multi_modal' in file_config:
            merged_config.enable_multi_modal = file_config['enable_multi_modal']
        if 'enable_input_sanitization' in file_config:
            merged_config.enable_input_sanitization = file_config['enable_input_sanitization']
        if 'enable_pii_scrubbing' in file_config:
            merged_config.enable_pii_scrubbing = file_config['enable_pii_scrubbing']
        if 'audit_logging' in file_config:
            merged_config.audit_logging = file_config['audit_logging']
        
        return merged_config
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate configuration parameters.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        errors = []
        
        # Validate AWS credentials
        aws_creds = config.get('aws_credentials', {})
        if not aws_creds.get('region'):
            errors.append("AWS region is required")
        
        # Validate AgentCore endpoints (skip if in test mode)
        endpoints = config.get('agentcore_endpoints', {})
        test_mode = endpoints.get('test_mode', False)
        
        if not test_mode:
            if not endpoints.get('browser_tool_endpoint') and not endpoints.get('base_url'):
                errors.append("AgentCore browser tool endpoint or base URL is required (unless test_mode is enabled)")
        # In test mode, validation is more lenient - we just need some endpoint configured
        
        # Validate browser configuration
        browser_config = config.get('browser_config', {})
        if browser_config.get('viewport_width', 0) <= 0:
            errors.append("Browser viewport width must be positive")
        if browser_config.get('viewport_height', 0) <= 0:
            errors.append("Browser viewport height must be positive")
        if browser_config.get('timeout_seconds', 0) <= 0:
            errors.append("Browser timeout must be positive")
        
        # Validate retry configuration
        retry_config = config.get('retry_config', {})
        if retry_config.get('max_attempts', 0) <= 0:
            errors.append("Retry max attempts must be positive")
        if retry_config.get('base_delay', 0) <= 0:
            errors.append("Retry base delay must be positive")
        
        if errors:
            raise ConfigurationError(f"Configuration validation failed: {'; '.join(errors)}")
        
        return True
    
    def get_aws_credentials(self) -> Dict[str, str]:
        """
        Get AWS credentials for AgentCore access.
        
        Returns:
            AWS credentials dictionary
            
        Raises:
            ConfigurationError: If credentials cannot be obtained
        """
        if not self._config:
            self.load_config()
        
        try:
            # Try to use configured credentials first
            if self._config.aws_credentials.access_key_id:
                return self._config.aws_credentials.to_dict()
            
            # Fall back to boto3 credential resolution
            if not self._aws_session:
                if self._config.aws_credentials.profile:
                    self._aws_session = boto3.Session(profile_name=self._config.aws_credentials.profile)
                else:
                    self._aws_session = boto3.Session()
            
            credentials = self._aws_session.get_credentials()
            if not credentials:
                raise ConfigurationError("No AWS credentials found")
            
            return {
                "aws_access_key_id": credentials.access_key,
                "aws_secret_access_key": credentials.secret_key,
                "aws_session_token": credentials.token,
                "region_name": self._config.aws_credentials.region
            }
            
        except (ClientError, NoCredentialsError) as e:
            raise ConfigurationError(f"Failed to get AWS credentials: {str(e)}") from e
    
    def get_browser_config(self) -> Dict[str, Any]:
        """
        Get browser configuration parameters.
        
        Returns:
            Browser configuration dictionary
        """
        if not self._config:
            self.load_config()
        
        return self._config.browser_config.to_dict()
    
    def get_agentcore_endpoints(self) -> Dict[str, str]:
        """
        Get AgentCore service endpoints.
        
        Returns:
            Endpoints dictionary
        """
        if not self._config:
            self.load_config()
        
        # Ensure endpoints are properly initialized
        self._config.agentcore_endpoints.__post_init__()
        
        endpoints = asdict(self._config.agentcore_endpoints)
        # Remove None values
        return {k: v for k, v in endpoints.items() if v is not None}
    
    def get_integration_config(self) -> IntegrationConfig:
        """
        Get complete integration configuration.
        
        Returns:
            IntegrationConfig instance
        """
        if not self._config:
            self.load_config()
        
        return self._config