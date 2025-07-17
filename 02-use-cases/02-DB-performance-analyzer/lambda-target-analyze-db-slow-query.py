import boto3
import os

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2'), 
    endpoint_url=os.getenv('ENDPOINT_URL')
)

lambda_target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": os.getenv('LAMBDA_ARN'),
            "toolSchema": {
                "inlinePayload": [
                    {
                        "name": "slow_query",
                        "description": "Analyzes slow running queries using pg_stat_statements. Get the environment from the user and use the action_type value as slow_query",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "connection_management_issues",
                        "description": "Analyzes connection management issues using pg_stat_statements. Get the environment from the user and use the action_type value as connection_management_issues",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "index_analysis",
                        "description": "Analyzes the index using pg_stat_statements. Get the environment from the user and use the action_type value as index_analysis",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "autovacuum_analysis",
                        "description": "Analyzes autovacuum using pg_stat_statements. Get the environment from the user and use the action_type value as autovacuum_analysis",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "io_analysis",
                        "description": "Analyzes IO issues in database using pg_stat_statements. Get the environment from the user and use the action_type value as io_analysis",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "replication_analysis",
                        "description": "Analyzes replciation issues using pg_stat_statements. Get the environment from the user and use the action_type value as replication_analysis",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "system_health",
                        "description": "Analyzes systems health using pg_stat_statements. Get the environment from the user and use the action_type value as system_health",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        }
                ]
            }
        }
    }
}

credential_config = [ 
    {
        "credentialProviderType" : "GATEWAY_IAM_ROLE"
    }
]
  

response = agentcore_client.create_gateway_target(
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'), # Replace with your GatewayID
    name=os.getenv('TARGET_NAME','pgstat-analyze-db'),
    description=os.getenv('TARGET_DESCRIPTION', 'PostgreSQL database performance analysis tool for Slow Query, Connection Issues, IO and Index analysis'),
    credentialProviderConfigurations=credential_config, 
    targetConfiguration=lambda_target_config)

print(f"Target ID: {response['targetId']}")
