
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
                        "name": "explain_query",
                        "description": "Analyzes and explains the execution plan for a given SQL query. Get the environment and query from the user and use the action_type value as explain_query. ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
                            }
                        },
                        {
                        "name": "extract_ddl",
                        "description": "Extracts the DDL (Data Definition Language) for a given database object. Get the environment, object_type (Type of the object like table, view, function, procedure etc..), object_name (The name of the database object to extract DDL for), object_schema (The schema of the database object to extract DDL for) from the user and use the action_type value as extract_ddl. ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                },
                                 "object_type": {
                                    "type": "string"
                                },
                                "object_name": {
                                    "type": "string"
                                },
                                "object_schema": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","object_type","object_name","object_schema"]
                            }
                        },
                        {
                        "name": "execute_query",
                        "description": "Execute read-only queries safely and return results with monitoring. Get the environment and query from the user and use the action_type value as execute_query. ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string"
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
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
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name=os.getenv('TARGET_NAME', 'pg-analyze-db-performance'),
    description=os.getenv('TARGET_DESCRIPTION', 'PostgreSQL database performance analysis tool with query execution plan analysis, DDL extraction, and safe read-only query execution capabilities'),
    credentialProviderConfigurations=credential_config, 
    targetConfiguration=lambda_target_config)


print(f"Target ID: {response['targetId']}")
