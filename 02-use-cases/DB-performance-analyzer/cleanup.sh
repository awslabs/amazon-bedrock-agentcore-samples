#!/bin/bash
set -e

# Parse command line arguments
DELETE_SECRETS=false

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --delete-secrets)
            DELETE_SECRETS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--delete-secrets]"
            exit 1
            ;;
    esac
done

echo "Cleaning up resources..."

# Load configurations if they exist
if [ -f config/gateway_config.env ]; then
    source config/gateway_config.env
fi
if [ -f config/target_config.env ]; then
    source config/target_config.env
fi
if [ -f config/cognito_config.env ]; then
    source config/cognito_config.env
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

# Delete Gateway Targets
if [ ! -z "$GATEWAY_IDENTIFIER" ]; then
    echo "Listing and deleting all Gateway Targets..."
    python3 -c "
import boto3
import os

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2')
)

try:
    # List all targets for the gateway
    response = agentcore_client.list_gateway_targets(
        gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER')
    )
    
    # Delete each target
    for target in response.get('items', []):
        target_id = target['targetId']
        print(f'Deleting target: {target_id}')
        agentcore_client.delete_gateway_target(
            gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
            targetId=target_id
        )
        print(f'Target {target_id} deleted successfully')
    
    # Also delete the specific target if provided
    if os.getenv('TARGET_ID') and os.getenv('TARGET_ID') not in [t['targetId'] for t in response.get('items', [])]:
        print(f'Deleting specific target: {os.getenv("TARGET_ID")}')
        agentcore_client.delete_gateway_target(
            gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
            targetId=os.getenv('TARGET_ID')
        )
        print(f'Target {os.getenv("TARGET_ID")} deleted successfully')
        
except Exception as e:
    print(f'Error with targets: {e}')
"
    
    # Wait for target deletion
    echo "Waiting for target deletion..."
    sleep 10
fi

# Delete Gateway
echo "Deleting Gateway..."
python3 -c "
import boto3
import os
import sys

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2')
)

# Try with the environment variable first
gateway_id = os.getenv('GATEWAY_IDENTIFIER')

# If not found, try to list all gateways and find one with a matching name
if not gateway_id:
    try:
        response = agentcore_client.list_gateways()
        for gateway in response.get('items', []):
            if 'DB-Performance-Analyzer-Gateway' in gateway.get('name', ''):
                gateway_id = gateway['gatewayId']
                print(f'Found gateway with ID: {gateway_id}')
                break
    except Exception as e:
        print(f'Error listing gateways: {e}')

if gateway_id:
    try:
        # List all targets for the gateway
        try:
            response = agentcore_client.list_gateway_targets(
                gatewayIdentifier=gateway_id
            )
            
            # Delete each target
            for target in response.get('items', []):
                target_id = target['targetId']
                print(f'Deleting target: {target_id}')
                agentcore_client.delete_gateway_target(
                    gatewayIdentifier=gateway_id,
                    targetId=target_id
                )
                print(f'Target {target_id} deleted successfully')
        except Exception as e:
            print(f'Error deleting targets: {e}')
        
        # Now delete the gateway
        agentcore_client.delete_gateway(
            gatewayIdentifier=gateway_id
        )
        print(f'Gateway {gateway_id} deleted successfully')
    except Exception as e:
        print(f'Error deleting gateway: {e}')
else:
    print('No gateway identifier found')
"

# Wait for gateway deletion
echo "Waiting for gateway deletion..."
sleep 10

# Delete Lambda functions
echo "Deleting Lambda functions..."
aws lambda delete-function \
    --function-name DBPerformanceAnalyzer \
    --region $AWS_REGION || echo "Failed to delete DBPerformanceAnalyzer Lambda function, continuing..."

aws lambda delete-function \
    --function-name PGStatAnalyzeDatabase \
    --region $AWS_REGION || echo "Failed to delete PGStatAnalyzeDatabase Lambda function, continuing..."

# Delete Lambda layer
echo "Deleting Lambda layer..."
if [ -f config/layer_config.env ]; then
    source config/layer_config.env
    if [ ! -z "$PSYCOPG2_LAYER_ARN" ]; then
        LAYER_NAME=$(echo $PSYCOPG2_LAYER_ARN | cut -d':' -f7)
        LAYER_VERSION=$(echo $PSYCOPG2_LAYER_ARN | cut -d':' -f8)
        aws lambda delete-layer-version \
            --layer-name $LAYER_NAME \
            --version-number $LAYER_VERSION \
            --region $AWS_REGION || echo "Failed to delete Lambda layer, continuing..."
    fi
fi

# Delete Lambda security group
echo "Cleaning up VPC resources..."
if [ -f config/vpc_config.env ]; then
    source config/vpc_config.env
    
    if [ ! -z "$LAMBDA_SECURITY_GROUP_ID" ] && [ ! -z "$DB_SECURITY_GROUP_IDS" ]; then
        # Remove inbound rules from DB security groups
        IFS=',' read -ra DB_SG_ARRAY <<< "$DB_SECURITY_GROUP_IDS"
        for DB_SG_ID in "${DB_SG_ARRAY[@]}"; do
            echo "Removing inbound rule from DB security group $DB_SG_ID"
            aws ec2 revoke-security-group-ingress \
                --group-id $DB_SG_ID \
                --protocol tcp \
                --port 5432 \
                --source-group $LAMBDA_SECURITY_GROUP_ID \
                --region $AWS_REGION || echo "Failed to remove inbound rule, continuing..."
        done
        
        # Delete Lambda security group
        # Clean up VPC endpoints first
        echo "Cleaning up VPC endpoints..."
        ./scripts/cleanup_vpc_endpoints.sh || echo "Failed to clean up VPC endpoints, continuing..."
        
        echo "Deleting Lambda security group $LAMBDA_SECURITY_GROUP_ID"
        aws ec2 delete-security-group \
            --group-id $LAMBDA_SECURITY_GROUP_ID \
            --region $AWS_REGION || echo "Failed to delete Lambda security group, continuing..."
    fi
fi

# Delete Cognito domain
if [ ! -z "$COGNITO_USERPOOL_ID" ] && [ ! -z "$COGNITO_DOMAIN_NAME" ]; then
    echo "Deleting Cognito domain..."
    aws cognito-idp delete-user-pool-domain \
        --domain $COGNITO_DOMAIN_NAME \
        --user-pool-id $COGNITO_USERPOOL_ID \
        --region $AWS_REGION || echo "Failed to delete domain, continuing..."
fi

# Delete Cognito user pool client
if [ ! -z "$COGNITO_USERPOOL_ID" ] && [ ! -z "$COGNITO_APP_CLIENT_ID" ]; then
    echo "Deleting Cognito user pool client..."
    aws cognito-idp delete-user-pool-client \
        --user-pool-id $COGNITO_USERPOOL_ID \
        --client-id $COGNITO_APP_CLIENT_ID \
        --region $AWS_REGION || echo "Failed to delete client, continuing..."
fi

# Delete Cognito user pool
if [ ! -z "$COGNITO_USERPOOL_ID" ]; then
    echo "Deleting Cognito user pool..."
    aws cognito-idp delete-user-pool \
        --user-pool-id $COGNITO_USERPOOL_ID \
        --region $AWS_REGION || echo "Failed to delete user pool, continuing..."
fi

# Delete IAM roles
echo "Deleting IAM roles..."

# Delete Lambda role
echo "Detaching policies from DBAnalyzerLambdaRole..."
# List and delete all inline policies
POLICIES=$(aws iam list-role-policies --role-name DBAnalyzerLambdaRole --query 'PolicyNames' --output json 2>/dev/null || echo "[]")
for POLICY in $(echo $POLICIES | jq -r '.[]'); do
    echo "Deleting inline policy: $POLICY"
    aws iam delete-role-policy --role-name DBAnalyzerLambdaRole --policy-name "$POLICY" || echo "Failed to delete policy $POLICY, continuing..."
done

# List and detach all managed policies
MANAGED_POLICIES=$(aws iam list-attached-role-policies --role-name DBAnalyzerLambdaRole --query 'AttachedPolicies[].PolicyArn' --output json 2>/dev/null || echo "[]")
for POLICY_ARN in $(echo $MANAGED_POLICIES | jq -r '.[]'); do
    echo "Detaching managed policy: $POLICY_ARN"
    aws iam detach-role-policy --role-name DBAnalyzerLambdaRole --policy-arn "$POLICY_ARN" || echo "Failed to detach policy $POLICY_ARN, continuing..."
done

# Now try to delete the role
echo "Deleting role: DBAnalyzerLambdaRole"
aws iam delete-role --role-name DBAnalyzerLambdaRole || echo "Failed to delete Lambda role, continuing..."

# Delete Gateway role
echo "Detaching policies from AgentCoreGatewayRole..."
# List and delete all inline policies
POLICIES=$(aws iam list-role-policies --role-name AgentCoreGatewayRole --query 'PolicyNames' --output json 2>/dev/null || echo "[]")
for POLICY in $(echo $POLICIES | jq -r '.[]'); do
    echo "Deleting inline policy: $POLICY"
    aws iam delete-role-policy --role-name AgentCoreGatewayRole --policy-name "$POLICY" || echo "Failed to delete policy $POLICY, continuing..."
done

# List and detach all managed policies
MANAGED_POLICIES=$(aws iam list-attached-role-policies --role-name AgentCoreGatewayRole --query 'AttachedPolicies[].PolicyArn' --output json 2>/dev/null || echo "[]")
for POLICY_ARN in $(echo $MANAGED_POLICIES | jq -r '.[]'); do
    echo "Detaching managed policy: $POLICY_ARN"
    aws iam detach-role-policy --role-name AgentCoreGatewayRole --policy-arn "$POLICY_ARN" || echo "Failed to detach policy $POLICY_ARN, continuing..."
done

# Now try to delete the role
echo "Deleting role: AgentCoreGatewayRole"
aws iam delete-role --role-name AgentCoreGatewayRole || echo "Failed to delete Gateway role, continuing..."

# Remove configuration files
echo "Removing configuration files..."
rm -f config/*.env

# Delete secrets and SSM parameters if requested
if [ "$DELETE_SECRETS" = true ]; then
    echo "Deleting secrets and SSM parameters..."
    
    # Load database configurations if they exist
    DB_SECRETS_TO_DELETE=()
    SSM_PARAMS_TO_DELETE=()
    
    if [ -f config/db_prod_config.env ]; then
        source config/db_prod_config.env
        if [ ! -z "$DB_SSM_PARAMETER" ]; then
            # Get secret name from SSM Parameter Store instead of config file
            SECRET_NAME=$(aws ssm get-parameter --name "$DB_SSM_PARAMETER" --query "Parameter.Value" --output text 2>/dev/null || echo "")
            if [ ! -z "$SECRET_NAME" ] && [ "$SECRET_NAME" != "None" ]; then
                DB_SECRETS_TO_DELETE+=("$SECRET_NAME")
            fi
            SSM_PARAMS_TO_DELETE+=("$DB_SSM_PARAMETER")
        fi
    fi
    
    if [ -f config/db_dev_config.env ]; then
        source config/db_dev_config.env
        if [ ! -z "$DB_SSM_PARAMETER" ]; then
            # Get secret name from SSM Parameter Store instead of config file
            SECRET_NAME=$(aws ssm get-parameter --name "$DB_SSM_PARAMETER" --query "Parameter.Value" --output text 2>/dev/null || echo "")
            if [ ! -z "$SECRET_NAME" ] && [ "$SECRET_NAME" != "None" ]; then
                DB_SECRETS_TO_DELETE+=("$SECRET_NAME")
            fi
            SSM_PARAMS_TO_DELETE+=("$DB_SSM_PARAMETER")
        fi
    fi
    
    # Delete secrets
    for SECRET_NAME in "${DB_SECRETS_TO_DELETE[@]}"; do
        echo "Deleting secret: $SECRET_NAME"
        aws secretsmanager delete-secret \
            --secret-id "$SECRET_NAME" \
            --force-delete-without-recovery \
            --region $AWS_REGION || echo "Failed to delete secret $SECRET_NAME, continuing..."
    done
    
    # Delete SSM parameters
    for PARAM_NAME in "${SSM_PARAMS_TO_DELETE[@]}"; do
        echo "Deleting SSM parameter: $PARAM_NAME"
        aws ssm delete-parameter \
            --name "$PARAM_NAME" \
            --region $AWS_REGION || echo "Failed to delete parameter $PARAM_NAME, continuing..."
    done
    
    # Database configuration files are removed with other config files
fi

echo "Cleanup completed"