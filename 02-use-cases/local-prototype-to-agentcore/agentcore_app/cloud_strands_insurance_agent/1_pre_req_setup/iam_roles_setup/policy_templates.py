#!/usr/bin/env python3
"""
Policy Templates for IAM Role Creation

This module provides templates for IAM trust and execution policies
needed for Bedrock AgentCore execution roles.
"""

import json
from typing import Dict, List, Any

def get_trust_policy(account_id: str) -> Dict[str, Any]:
    """
    Generate the trust policy document for the AgentCore execution role
    
    Args:
        account_id: The AWS account ID
        
    Returns:
        Dictionary containing the trust policy document
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicyProd",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:*:{account_id}:*"
                    }
                }
            },
        ]
    }

def get_ecr_policy(account_id: str, regions: List[str], repository_name: str = 'bedrock-agentcore') -> Dict[str, Any]:
    """
    Generate the ECR access policy statements
    
    Args:
        account_id: The AWS account ID
        regions: List of AWS regions
        repository_name: ECR repository name
        
    Returns:
        Dictionary containing the ECR policy statements
    """
    # ECR image access statement
    ecr_image_access = {
        "Sid": "ECRImageAccess",
        "Effect": "Allow",
        "Action": [
            "ecr:BatchGetImage",
            "ecr:GetDownloadUrlForLayer"
        ],
        "Resource": [f"arn:aws:ecr:{region}:{account_id}:repository/{repository_name}" for region in regions]
    }
    
    # ECR token access statement
    ecr_token_access = {
        "Sid": "ECRTokenAccess",
        "Effect": "Allow",
        "Action": [
            "ecr:GetAuthorizationToken"
        ],
        "Resource": "*"
    }
    
    return [ecr_image_access, ecr_token_access]

def get_logs_policy(account_id: str, regions: List[str]) -> List[Dict[str, Any]]:
    """
    Generate the CloudWatch Logs access policy statements
    
    Args:
        account_id: The AWS account ID
        regions: List of AWS regions
        
    Returns:
        List of dictionaries containing the Logs policy statements
    """
    # Log group creation and stream description
    log_group_access = {
        "Effect": "Allow",
        "Action": [
            "logs:DescribeLogStreams",
            "logs:CreateLogGroup"
        ],
        "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*" for region in regions]
    }
    
    # Log group description
    log_group_describe = {
        "Effect": "Allow",
        "Action": [
            "logs:DescribeLogGroups"
        ],
        "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:*" for region in regions]
    }
    
    # Log stream creation and event writing
    log_stream_access = {
        "Effect": "Allow",
        "Action": [
            "logs:CreateLogStream",
            "logs:PutLogEvents"
        ],
        "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*" for region in regions]
    }
    
    return [log_group_access, log_group_describe, log_stream_access]

def get_xray_policy() -> Dict[str, Any]:
    """
    Generate the X-Ray access policy statement
    
    Returns:
        Dictionary containing the X-Ray policy statement
    """
    return {
        "Effect": "Allow", 
        "Action": [ 
            "xray:PutTraceSegments", 
            "xray:PutTelemetryRecords", 
            "xray:GetSamplingRules", 
            "xray:GetSamplingTargets"
        ],
        "Resource": "*" 
    }

def get_cloudwatch_policy() -> Dict[str, Any]:
    """
    Generate the CloudWatch Metrics access policy statement
    
    Returns:
        Dictionary containing the CloudWatch policy statement
    """
    return {
        "Effect": "Allow",
        "Resource": "*",
        "Action": "cloudwatch:PutMetricData",
        "Condition": {
            "StringEquals": {
                "cloudwatch:namespace": "bedrock-agentcore"
            }
        }
    }

def get_bedrock_agentcore_policy(account_id: str, regions: List[str], agent_name: str = 'insurance-agent') -> Dict[str, Any]:
    """
    Generate the Bedrock AgentCore access policy statement
    
    Args:
        account_id: The AWS account ID
        regions: List of AWS regions
        agent_name: Name of the agent
        
    Returns:
        Dictionary containing the Bedrock AgentCore policy statement
    """
    resources = []
    
    for region in regions:
        resources.extend([
            f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
            f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*"
        ])
    
    return {
        "Sid": "GetAgentAccessToken",
        "Effect": "Allow",
        "Action": [
            "bedrock-agentcore:GetWorkloadAccessToken",
            "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
            "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
        ],
        "Resource": resources
    }

def get_bedrock_models_policy(account_id: str, regions: List[str]) -> Dict[str, Any]:
    """
    Generate the Bedrock Models access policy statement
    
    Args:
        account_id: The AWS account ID
        regions: List of AWS regions
        
    Returns:
        Dictionary containing the Bedrock Models policy statement
    """
    return {
        "Sid": "BedrockModelInvocation", 
        "Effect": "Allow", 
        "Action": [ 
            "bedrock:InvokeModel", 
            "bedrock:InvokeModelWithResponseStream"
        ], 
        "Resource": [
            "arn:aws:bedrock:*::foundation-model/*",
            *[f"arn:aws:bedrock:{region}:{account_id}:*" for region in regions]
        ]
    }

def build_execution_policy(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """
    Build the complete execution policy document based on configuration
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        Dictionary containing the complete execution policy
    """
    from config import get_account_id, get_regions
    
    account_id = get_account_id(config_data)
    regions = get_regions(config_data)
    repository_name = config_data.get('ecr', {}).get('repository_name', 'bedrock-agentcore')
    agent_name = config_data.get('agent', {}).get('name', 'insurance-agent')
    
    # Initialize policy statements list
    statements = []
    
    # Add enabled policy statements based on configuration
    policies = config_data.get('policies', {})
    
    if policies.get('enable_ecr', 'true').lower() == 'true':
        ecr_policies = get_ecr_policy(account_id, regions, repository_name)
        statements.extend(ecr_policies)
        
    if policies.get('enable_logs', 'true').lower() == 'true':
        logs_policies = get_logs_policy(account_id, regions)
        statements.extend(logs_policies)
        
    if policies.get('enable_xray', 'true').lower() == 'true':
        statements.append(get_xray_policy())
        
    if policies.get('enable_cloudwatch', 'true').lower() == 'true':
        statements.append(get_cloudwatch_policy())
        
    if policies.get('enable_bedrock_agentcore', 'true').lower() == 'true':
        statements.append(get_bedrock_agentcore_policy(account_id, regions, agent_name))
        
    if policies.get('enable_bedrock_models', 'true').lower() == 'true':
        statements.append(get_bedrock_models_policy(account_id, regions))
    
    # Create the complete policy document
    policy_document = {
        "Version": "2012-10-17",
        "Statement": statements
    }
    
    return policy_document

def write_policy_files(config_data: Dict[str, Dict[str, str]], output_dir: str = '.') -> Dict[str, str]:
    """
    Write policy documents to files
    
    Args:
        config_data: Configuration dictionary
        output_dir: Directory to write files to
        
    Returns:
        Dictionary with paths to created files
    """
    import os
    from config import get_account_id
    
    account_id = get_account_id(config_data)
    
    # Create trust policy document
    trust_policy = get_trust_policy(account_id)
    trust_policy_path = os.path.join(output_dir, "trust-policy.json")
    
    with open(trust_policy_path, 'w') as f:
        json.dump(trust_policy, f, indent=2)
    
    # Create execution policy document
    execution_policy = build_execution_policy(config_data)
    execution_policy_path = os.path.join(output_dir, "execution-policy.json")
    
    with open(execution_policy_path, 'w') as f:
        json.dump(execution_policy, f, indent=2)
    
    return {
        "trust_policy": trust_policy_path,
        "execution_policy": execution_policy_path
    }