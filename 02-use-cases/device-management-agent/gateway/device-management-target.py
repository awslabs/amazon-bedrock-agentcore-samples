import boto3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables without fallback values
AWS_REGION = os.getenv('AWS_REGION')
#ENDPOINT_URL = os.getenv('ENDPOINT_URL')
GATEWAY_IDENTIFIER = os.getenv('GATEWAY_IDENTIFIER')
LAMBDA_ARN = os.getenv('LAMBDA_ARN')
TARGET_NAME = os.getenv('TARGET_NAME')
TARGET_DESCRIPTION = os.getenv('TARGET_DESCRIPTION')

bedrock_agent_core_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=AWS_REGION
    #endpoint_url=ENDPOINT_URL
)

lambda_target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": LAMBDA_ARN,
            "toolSchema": {
                "inlinePayload": [
                    {
                        "name": "list_devices",
                        "description": "To list the devices. use action_name default parameter value as 'list_devices'",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name"]
                            }
                        },
                        {
                        "name": "get_device_settings",
                        "description": "To list the devices. use action_name default parameter value as 'get_device_settings'. You need to get teh device_id from the user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "device_id": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id"]
                            }
                        },
                        {
                        "name": "list_wifi_networks",
                        "description": "To list the devices. use action_name default parameter value as 'list_wifi_networks'. You need to get teh device_id from the user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "device_id": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id"]
                            }
                        },
                        {
                        "name": "list_users",
                        "description": "To list the devices. use action_name default parameter value as 'list_users'",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name"]
                            }
                        },
                        {
                        "name": "query_user_activity",
                        "description": "To list the devices. use action_name default parameter value as 'query_user_activity'. Please get start_date, end_date, user_id and activity_type from the user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "start_date": {
                                    "type": "string"
                                },
                                "end_date": {
                                    "type": "string"
                                },
                                "user_id": {
                                    "type": "string"
                                },
                                "activity_type": {
                                    "type": "string"
                                }               
                            },
                            "required": ["action_name","start_date","end_date"]
                            }
                        },
                        {
                        "name": "update_wifi_ssid",
                        "description": "To list the devices. use action_name default parameter value as 'update_wifi_ssid'. Get device_id, network_id and ssid from the user if not given in the context. ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "device_id": {
                                    "type": "string"
                                },
                                "network_id": {
                                    "type": "string"
                                },
                                "ssid": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id","network_id","ssid"]
                            }
                        },
                        {
                        "name": "update_wifi_security",
                        "description": "To list the devices. use action_name default parameter value as 'update_wifi_security'. Get device_id, network_id and security_type from the user if not given in the context.  ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                 "device_id": {
                                    "type": "string"
                                },
                                 "network_id": {
                                    "type": "string"
                                },
                                 "security_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id","network_id","security_type"]
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

response = bedrock_agent_core_client.create_gateway_target(
    gatewayIdentifier=GATEWAY_IDENTIFIER,
    name=TARGET_NAME,
    description=TARGET_DESCRIPTION,
    credentialProviderConfigurations=credential_config, 
    targetConfiguration=lambda_target_config)

print(f"Target ID: {response['targetId']}")
