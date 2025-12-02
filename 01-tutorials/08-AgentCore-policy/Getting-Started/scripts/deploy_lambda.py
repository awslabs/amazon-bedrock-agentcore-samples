"""
Deploy RefundTool Lambda function
Automatically creates and deploys the Lambda function for the demo
"""

import boto3
import json
import zipfile
import io
import sys
from pathlib import Path
from botocore.exceptions import ClientError

def get_or_create_lambda_role(iam_client, role_name='RefundToolLambdaRole'):
    """Get existing Lambda execution role or create a new one"""
    
    try:
        # Try to get existing role
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        print(f"✅ Using existing IAM role: {role_name}")
        print(f"   ARN: {role_arn}")
        return role_arn
        
    except iam_client.exceptions.NoSuchEntityException:
        # Role doesn't exist, create it
        print(f"📝 Creating IAM role: {role_name}...")
        
        # Trust policy for Lambda
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        try:
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Execution role for RefundTool Lambda function'
            )
            role_arn = response['Role']['Arn']
            print(f"✅ IAM role created: {role_arn}")
            
            # Attach basic Lambda execution policy
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
            )
            print("✅ Attached AWSLambdaBasicExecutionRole policy")
            
            # Wait a bit for IAM propagation
            print("⏳ Waiting 10 seconds for IAM propagation...")
            import time
            time.sleep(10)
            
            return role_arn
            
        except Exception as e:
            print(f"❌ Error creating IAM role: {e}")
            raise

def create_lambda_deployment_package():
    """Create a deployment package with the Lambda function code"""
    
    # Lambda function code
    lambda_code = '''console.log('Loading RefundTool function');

export const handler = async (event, context) => {
    console.log('event =', JSON.stringify(event));
    console.log('context =', JSON.stringify(context));
    
    var response = undefined;
    
    if (event.body !== undefined) {
        // API Gateway format
        console.log('event.body =', event.body);
        const body = JSON.parse(event.body);
        response = {
            "status": "SUCCESS",
            "message": `Refund processed successfully: $${body.amount} for order ${body.orderId}`,
            "amount": body.amount,
            "orderId": body.orderId
        };
    } else {
        // Direct invocation from Gateway
        response = {
            "status": "SUCCESS",
            "message": `Refund processed successfully: $${event.amount} for order ${event.orderId}`,
            "amount": event.amount,
            "orderId": event.orderId
        };
        return response;
    }
    
    console.log('response =', JSON.stringify(response));
    return {"statusCode": 200, "body": JSON.stringify(response)};
};
'''
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('index.mjs', lambda_code)
    
    zip_buffer.seek(0)
    return zip_buffer.read()

def deploy_lambda_function(function_name='RefundTool', region='us-east-1'):
    """Deploy the RefundTool Lambda function"""
    
    print("🚀 Deploying RefundTool Lambda Function")
    print("=" * 60)
    
    # Initialize AWS clients
    lambda_client = boto3.client('lambda', region_name=region)
    iam_client = boto3.client('iam', region_name=region)
    
    # Step 1: Get or create IAM role
    print("\n📝 Step 1: Setting up IAM role...")
    try:
        role_arn = get_or_create_lambda_role(iam_client)
    except Exception as e:
        print(f"\n❌ Failed to setup IAM role: {e}")
        print("\n💡 Alternative: Provide your own Lambda execution role ARN")
        role_arn = input("Enter Lambda execution role ARN (or press Enter to exit): ").strip()
        if not role_arn:
            sys.exit(1)
    
    # Step 2: Create deployment package
    print("\n📝 Step 2: Creating deployment package...")
    deployment_package = create_lambda_deployment_package()
    print(f"✅ Deployment package created ({len(deployment_package)} bytes)")
    
    # Step 3: Check if Lambda function exists
    print(f"\n📝 Step 3: Checking if Lambda function '{function_name}' exists...")
    function_exists = False
    
    try:
        response = lambda_client.get_function(FunctionName=function_name)
        function_exists = True
        lambda_arn = response['Configuration']['FunctionArn']
        print(f"✅ Function already exists: {lambda_arn}")
        
        # Ask if user wants to update
        update = input("\n❓ Update existing function? (y/N): ").strip().lower()
        if update == 'y':
            print("\n📝 Updating function code...")
            response = lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=deployment_package
            )
            print("✅ Function code updated")
            lambda_arn = response['FunctionArn']
        
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"📝 Function does not exist, creating new function...")
        
        # Create new Lambda function
        try:
            response = lambda_client.create_function(
                FunctionName=function_name,
                Runtime='nodejs24.x',
                Role=role_arn,
                Handler='index.handler',
                Code={'ZipFile': deployment_package},
                Description='Refund processing tool for AgentCore Policy demo',
                Timeout=30,
                MemorySize=128,
                Publish=True
            )
            
            lambda_arn = response['FunctionArn']
            print(f"✅ Lambda function created successfully!")
            print(f"   ARN: {lambda_arn}")
            
        except Exception as e:
            print(f"❌ Error creating Lambda function: {e}")
            sys.exit(1)
    
    # Step 4: Save Lambda ARN to config file
    print("\n📝 Step 4: Saving configuration...")
    config_file = Path(__file__).parent / 'lambda_config.json'
    config = {
        'lambda_arn': lambda_arn,
        'function_name': function_name,
        'region': region
    }
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Configuration saved to: {config_file}")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ LAMBDA DEPLOYMENT COMPLETE!")
    print("=" * 60)
    print(f"Function Name: {function_name}")
    print(f"Function ARN:  {lambda_arn}")
    print(f"Region:        {region}")
    print(f"Runtime:       nodejs24.x")
    print(f"Handler:       index.handler")
    print("=" * 60)
    
    return lambda_arn

def main():
    """Main function"""
    try:
        lambda_arn = deploy_lambda_function()
        print("\n🎉 Lambda function is ready for use!")
        print("\n💡 Next step: Run setup_gateway.py to create the gateway")
        return lambda_arn
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
