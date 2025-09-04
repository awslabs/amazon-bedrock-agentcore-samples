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
                        "description": "Analyzes and explains the execution plan for a SQL query to help optimize database performance. Provide the database environment (dev/prod) and the SQL query to analyze. Use action_type default value as explain_query.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'explain_query' for this tool."
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
                        "description": "Extracts the DDL (Data Definition Language) for a database object. Provide the environment (dev/prod), object_type (table, view, function, etc.), object_name, and object_schema to get the creation script. Use action_type default value as extract_ddl.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'extract_ddl' for this tool."
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
                        "description": "Executes a read-only SQL query safely and returns the results with performance metrics. Provide the environment (dev/prod) and the SQL query to execute. Use action_type default value as execute_query.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'execute_query' for this tool."
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
                            }
                        },
                        {
                        "name": "enhanced_query_diagnostics",
                        "description": "Provides comprehensive query diagnostics including execution plan analysis, buffer usage, database statistics, and performance metrics. Based on enhanced diagnostics from runbooks.py. Provide the environment (dev/prod) and SQL query to analyze. Use action_type default value as enhanced_query_diagnostics.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'enhanced_query_diagnostics' for this tool."
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
                            }
                        },
                        {
                        "name": "performance_insights_analysis",
                        "description": "Provides Performance Insights-style analysis including top queries by execution time, wait events analysis, and database load metrics. Based on comprehensive diagnostics from runbooks.py. Provide the environment (dev/prod) to analyze. Use action_type default value as performance_insights_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'performance_insights_analysis' for this tool."
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
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name=os.getenv('TARGET_NAME', 'pg-analyze-db-performance'),
    description=os.getenv('TARGET_DESCRIPTION', 'Enhanced PostgreSQL database performance analysis tool with comprehensive query execution plan analysis, DDL extraction, safe read-only query execution, enhanced query diagnostics with buffer usage analysis, and Performance Insights-style metrics. Based on production-ready runbooks with deep diagnostic capabilities.'),
    credentialProviderConfigurations=credential_config, 
    targetConfiguration=lambda_target_config)

target_id = response['targetId']
print(f"Target ID: {target_id}")

# Create target_config.env file
with open('target_config.env', 'w') as f:
    f.write(f"TARGET_ID={target_id}\n")
