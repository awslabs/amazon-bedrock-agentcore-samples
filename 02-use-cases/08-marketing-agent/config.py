"""
Configuration management for the NL2SQL agent.
"""
import os
import logging
from typing import Dict, Any


def setup_logging(level=logging.INFO):
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_config() -> Dict[str, Any]:
    """
    Get configuration from environment variables.
    
    Returns:
        Dict containing configuration values
    """
    config = {
        # AWS Configuration
        "aws_region": os.environ.get("AWS_REGION", "us-west-2"),  # Default to us-west-2
        
        # Athena Configuration
        "athena_database": os.environ.get("ATHENA_DATABASE", ""),
        "athena_output_location": os.environ.get("ATHENA_OUTPUT_LOCATION", ""),
        
        # Knowledge Base Configuration
        "knowledge_base_id": os.environ.get("KNOWLEDGE_BASE_ID", ""),

    }
    
    return config
