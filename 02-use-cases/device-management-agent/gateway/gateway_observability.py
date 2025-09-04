import boto3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def enable_observability_for_resource(resource_arn, resource_id, account_id, region='us-west-2'):
    """
    Enable observability for a Bedrock AgentCore resource (e.g., Gateway)
    """
    logs_client = boto3.client('logs', region_name=region)

    # Step 0: Create new log group for vended log delivery
    log_group_name = f'/aws/vendedlogs/bedrock-agentcore/{resource_id}'
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
        print(f"Created log group: {log_group_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"Log group already exists: {log_group_name}")
    except Exception as e:
        print(f"Error creating log group: {e}")
        return None
        
    log_group_arn = f'arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}'
    
    try:
        # Step 3: Create delivery destinations
        logs_destination_response = logs_client.put_delivery_destination(
            name=f"{resource_id}-logs-destination",
            deliveryDestinationType='CWL',
            deliveryDestinationConfiguration={
                'destinationResourceArn': log_group_arn,
            }
        )
        print(f"Created logs delivery destination: {logs_destination_response['deliveryDestination']['name']}")
        
        print(f"Observability enabled for {resource_id}")
        return resource_id
        
    except Exception as e:
        print(f"Error enabling observability: {e}")
        return None

if __name__ == "__main__":
    # Get environment variables
    gateway_arn = os.getenv('GATEWAY_ARN')
    gateway_id = os.getenv('GATEWAY_ID')
    aws_region = os.getenv('AWS_REGION', 'us-west-2')
    
    # Get AWS account ID
    try:
        sts_client = boto3.client('sts', region_name=aws_region)
        account_id = sts_client.get_caller_identity()['Account']
        print(f"AWS Account ID: {account_id}")
    except Exception as e:
        print(f"Error getting AWS account ID: {e}")
        exit(1)
    
    # Validate required environment variables
    if not gateway_arn:
        print("Error: GATEWAY_ARN not found in environment variables")
        exit(1)
    
    if not gateway_id:
        print("Error: GATEWAY_ID not found in environment variables")
        exit(1)
    
    print(f"Gateway ARN: {gateway_arn}")
    print(f"Gateway ID: {gateway_id}")
    print(f"Region: {aws_region}")
    
    # Enable observability for the gateway
    enable_observability_for_resource(gateway_arn, gateway_id, account_id, aws_region)