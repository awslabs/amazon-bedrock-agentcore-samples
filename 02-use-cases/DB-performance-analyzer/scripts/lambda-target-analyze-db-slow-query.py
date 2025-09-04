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
                        "description": "Identifies and analyzes the slowest queries in your database using pg_stat_statements. Provide the environment (dev/prod) to analyze slow queries. Use action_type default value as slow_query.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'slow_query' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "conn_issues",
                        "description": "Detects and analyzes database connection issues such as idle connections, connection leaks, and connection pool problems. Provide the environment (dev/prod) to analyze. Use action_type default value as connection_management_issues.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'connection_management_issues' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "index_analysis",
                        "description": "Evaluates database index usage, identifies missing or unused indexes, and provides optimization recommendations. Provide the environment (dev/prod) to analyze indexes. Use action_type default value as index_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'index_analysis' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "autovacuum_analysis",
                        "description": "Examines PostgreSQL autovacuum performance, dead tuple accumulation, and provides configuration recommendations. Provide the environment (dev/prod) to analyze autovacuum settings. Use action_type default value as autovacuum_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'autovacuum_analysis' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "io_analysis",
                        "description": "Analyzes database I/O patterns, buffer usage, and checkpoint activity to identify performance bottlenecks. Provide the environment (dev/prod) to analyze I/O performance. Use action_type default value as io_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'io_analysis' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "replication_analysis",
                        "description": "Monitors PostgreSQL replication status, lag, and health to ensure high availability. Provide the environment (dev/prod) to analyze replication performance. Use action_type default value as replication_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'replication_analysis' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "system_health",
                        "description": "Provides a comprehensive health check of your PostgreSQL database including cache hit ratios, deadlocks, and long-running transactions. Provide the environment (dev/prod) to analyze system health. Use action_type default value as system_health.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'system_health' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "vacuum_progress",
                        "description": "Monitors current vacuum operations progress including phase, duration, and completion percentage. Based on comprehensive diagnostics from runbooks.py. Provide the environment (dev/prod) to analyze vacuum progress. Use action_type default value as vacuum_progress.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'vacuum_progress' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "xid_analysis",
                        "description": "Analyzes transaction ID (XID) wraparound status, oldest XIDs across databases, and tables needing vacuum to prevent wraparound. Based on comprehensive diagnostics from runbooks.py. Provide the environment (dev/prod) to analyze XID status. Use action_type default value as xid_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'xid_analysis' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "bloat_analysis",
                        "description": "Identifies tables with significant bloat, calculates bloat percentages and wasted space. Based on comprehensive diagnostics from runbooks.py. Provide the environment (dev/prod) to analyze table bloat. Use action_type default value as bloat_analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'bloat_analysis' for this tool."
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "long_running_transactions",
                        "description": "Identifies long-running transactions that may be blocking vacuum operations or causing performance issues. Based on comprehensive diagnostics from runbooks.py. Provide the environment (dev/prod) to analyze long-running transactions. Use action_type default value as long_running_transactions.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "The type of action to perform. Use 'long_running_transactions' for this tool."
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
    description=os.getenv('TARGET_DESCRIPTION', 'Enhanced PostgreSQL database performance analyzer with comprehensive diagnostics including slow queries, connection issues, I/O bottlenecks, index usage, autovacuum, replication, system health, vacuum progress monitoring, XID wraparound analysis, table bloat detection, and long-running transaction identification. Based on production-ready runbooks with deep diagnostic capabilities.'),
    credentialProviderConfigurations=credential_config, 
    targetConfiguration=lambda_target_config)

print(f"Target ID: {response['targetId']}")
