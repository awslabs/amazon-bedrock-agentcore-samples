import boto3
import os
import sys

# Get the script directory and project directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2'), 
    endpoint_url=os.getenv('ENDPOINT_URL')
)

# Load Lambda ARNs
config_file = os.path.join(project_dir, "config", "lambda_config.env")
if not os.path.exists(config_file):
    print(f"Error: Lambda config file not found at {config_file}")
    sys.exit(1)

with open(config_file, 'r') as f:
    for line in f:
        if line.startswith('export '):
            key, value = line.replace('export ', '').strip().split('=', 1)
            os.environ[key] = value.strip('"\'')


lambda_target_config = {
    'mcp': {
        'lambda': {
            'lambdaArn': os.getenv('LAMBDA_ARN'),
            'toolSchema': {
                'inlinePayload': [
                    {
                        'name': 'explain_query',
                        'description': 'Analyzes and explains the execution plan for a given SQL query.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'},
                                'query': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type', 'query']
                        }
                    },
                    {
                        'name': 'extract_ddl',
                        'description': 'Extracts the DDL for a given database object.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'},
                                'object_type': {'type': 'string'},
                                'object_name': {'type': 'string'},
                                'object_schema': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type', 'object_type', 'object_name', 'object_schema']
                        }
                    },
                    {
                        'name': 'execute_query',
                        'description': 'Execute read-only queries safely and return results.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'},
                                'query': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type', 'query']
                        }
                    }
                ]
            }
        }
    }
}

credential_config = [
    {
        'credentialProviderType': 'GATEWAY_IAM_ROLE'
    }
]

# Create DB Performance Analyzer target
response = agentcore_client.create_gateway_target(
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name=os.getenv('TARGET_NAME', 'db-performance-analyzer'),
    description=os.getenv('TARGET_DESCRIPTION', 'DB Performance Analyzer tools'),
    credentialProviderConfigurations=credential_config,
    targetConfiguration=lambda_target_config
)

print(f"DB Performance Analyzer target created with ID: {response['targetId']}")

# Save Target configuration to file
target_config_file = os.path.join(project_dir, "config", "target_config.env")
with open(target_config_file, 'w') as f:
    f.write(f"export TARGET_ID={response['targetId']}\n")

# Create PGStat target configuration
pgstat_target_config = {
    'mcp': {
        'lambda': {
            'lambdaArn': os.getenv('PGSTAT_LAMBDA_ARN'),
            'toolSchema': {
                'inlinePayload': [
                    {
                        'name': 'slow_query',
                        'description': 'Analyzes slow queries in the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'connection_management_issues',
                        'description': 'Analyzes connection management issues in the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'index_analysis',
                        'description': 'Analyzes index usage and efficiency in the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'autovacuum_analysis',
                        'description': 'Analyzes autovacuum performance in the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'io_analysis',
                        'description': 'Analyzes I/O performance in the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'replication_analysis',
                        'description': 'Analyzes replication status in the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'system_health',
                        'description': 'Analyzes overall system health of the PostgreSQL database.',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    }
                ]
            }
        }
    }
}

# Create PGStat target
pgstat_response = agentcore_client.create_gateway_target(
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name='pgstat-analyzer',
    description='PostgreSQL statistics and performance analysis tools',
    credentialProviderConfigurations=credential_config,
    targetConfiguration=pgstat_target_config
)

print(f"PGStat target created with ID: {pgstat_response['targetId']}")

# Save PGStat Target configuration to file
pgstat_config_file = os.path.join(project_dir, "config", "pgstat_target_config.env")
with open(pgstat_config_file, 'w') as f:
    f.write(f"export PGSTAT_TARGET_ID={pgstat_response['targetId']}\n")