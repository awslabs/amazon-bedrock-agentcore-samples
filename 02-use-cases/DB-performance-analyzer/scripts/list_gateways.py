import boto3
import os
import json

# Get environment variables
REGION = os.environ.get('AWS_REGION')

# Create the agentcore client
agentcore_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

try:
    # List gateways
    print("Listing existing gateways...")
    gateways = agentcore_client.list_gateways()
    
    # Print gateway details
    for gateway in gateways.get('gateways', []):
        gateway_id = gateway.get('gatewayId')
        gateway_name = gateway.get('name')
        gateway_arn = gateway.get('gatewayArn')
        
        print(f"Gateway ID: {gateway_id}")
        print(f"Gateway Name: {gateway_name}")
        print(f"Gateway ARN: {gateway_arn}")
        print("-" * 50)
        
        # If this is our target gateway, save the details
        if gateway_name == "DB-Performance-Analyzer-Gateway":
            print(f"Found our target gateway: {gateway_name}")
            
            # Construct the gateway endpoint
            gateway_endpoint = f"https://{gateway_id}.gateway.bedrock-agentcore.{REGION}.amazonaws.com"
            
            # Save Gateway configuration to file
            with open('gateway_config.json', 'w') as f:
                json.dump({
                    "GATEWAY_ID": gateway_id,
                    "GATEWAY_ARN": gateway_arn,
                    "GATEWAY_ENDPOINT": gateway_endpoint
                }, f)
            
            print("Gateway configuration saved to gateway_config.json")
    
    if not gateways.get('gateways'):
        print("No gateways found")
        
except Exception as e:
    print(f"Error listing gateways: {e}")
    exit(1)