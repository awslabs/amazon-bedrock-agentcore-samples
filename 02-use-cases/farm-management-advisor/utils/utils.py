import boto3
import json
import time
from boto3.session import Session
import zipfile
import os
import tempfile
import subprocess



boto_session = Session()
region = boto_session.region_name
account_id = boto3.client("sts").get_caller_identity()["Account"]

lambda_client = boto3.client('lambda', region_name=region)
iam_client = boto3.client('iam')



def create_agentcore_role(agent_name):
    agentcore_role_name = f'agentcore-{agent_name}-role'
    
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer"
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogStreams",                   
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:*"
                ]
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": "*"
            },
            {
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets"
                ],
             "Resource": [ "*" ]
             },
             {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                "Resource": [
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/*"
                ]
            },
            {
                "Sid": "MemoryPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateMemory",
                    "bedrock-agentcore:DeleteMemory",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:ListMemories",
                    "bedrock-agentcore:SaveConversation",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:UpdateMemory",
                    "bedrock-agentcore:CreateEvent",
                    "iam:PassRole"
                ],
                "Resource": "*"
            }
        ]
    }
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
                
            },
            
            {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock-agentcore.amazonaws.com"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": account_id
                },
                "ArnLike": {
                    "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                }
            }
        }
            
        ]
    }
    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )
    role_policy_document = json.dumps(role_policy)
    # Create IAM Role for the Lambda function
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )
        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_role_name,
            MaxItems=100
        )


        # Detach all managed policies
        attached_policies = iam_client.list_attached_role_policies(
            RoleName=agentcore_role_name
        )
        for policy in attached_policies['AttachedPolicies']:
            print(f"  Detaching: {policy['PolicyName']}")
            iam_client.detach_role_policy(
                RoleName=agentcore_role_name,
                PolicyArn=policy['PolicyArn']
            )
        
        # Delete all inline policies
        inline_policies = iam_client.list_role_policies(
            RoleName=agentcore_role_name
        )
        for policy_name in inline_policies['PolicyNames']:
            print(f"  Deleting: {policy_name}")
            iam_client.delete_role_policy(
                RoleName=agentcore_role_name,
                PolicyName=policy_name
            )
            
        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_role_name,
                PolicyName=policy_name
            )
        print(f"deleting {agentcore_role_name}")
        iam_client.delete_role(
            RoleName=agentcore_role_name
        )
        print(f"recreating {agentcore_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )
    # Attach the AWSLambdaBasicExecutionRole policy
    print(f"attaching role policy {agentcore_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name
        )

        # Attach the managed policy
        iam_client.attach_role_policy(
            RoleName=agentcore_role_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonBedrockAgentCoreMemoryBedrockModelInferenceExecutionRolePolicy"
        )
    except Exception as e:
        print(e)
    return agentcore_iam_role

def create_agentcore_mem_role(agent_mem_name):

    role_name = f'agentcore-mem-{agent_mem_name}-role'
    
    # Define trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for Bedrock Agent Core Memory operations"
        )
        
        # Attach the managed policy
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonBedrockAgentCoreMemoryBedrockModelInferenceExecutionRolePolicy"
        )
        
        role_arn = response['Role']['Arn']
        print(f"Role created successfully: {role_arn}")
        
    except iam_client.exceptions.EntityAlreadyExistsException:
        # Role already exists, get its ARN
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response['Role']['Arn']
        print(f"Role already exists: {role_arn}")

    return role_arn




def create_lambda_role(lambda_role_name):
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
    
    lambda_policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["logs:*", "bedrock:*", "bedrock-runtime:*","s3:GetObject", "s3:PutObject"], "Resource": "*"}
    ]}
    
    # Create the role
    try:
        role_response = iam_client.create_role(
            RoleName=lambda_role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy))
        print(f"✓ Created IAM role: {lambda_role_name}")
        iam_client.put_role_policy(
            RoleName=lambda_role_name,
            PolicyName=f'{lambda_role_name}Policy', 
            PolicyDocument=json.dumps(lambda_policy)
        )
        
        # Attach basic Lambda execution policy
        iam_client.attach_role_policy(
            RoleName=lambda_role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"✓ IAM role {lambda_role_name} already exists")
        role_response = iam_client.get_role(RoleName=lambda_role_name)

    return role_response

# Create deployment package
def create_lambda_layer(packages, layer_name):
    
    with tempfile.TemporaryDirectory() as temp_dir:
        python_dir = os.path.join(temp_dir, 'python')
        os.makedirs(python_dir)
        
        # Install packages
        subprocess.run([
            'pip', 'install', '--target', python_dir
        ] + packages, check=True)
        
        # Create layer zip
        layer_zip_path = os.path.join(temp_dir, 'layer.zip')
        with zipfile.ZipFile(layer_zip_path, 'w') as zip_file:
            for root, dirs, files in os.walk(python_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_path = os.path.relpath(file_path, temp_dir)
                    zip_file.write(file_path, arc_path)
        
        # Upload layer
        with open(layer_zip_path, 'rb') as zip_data:
            layer_response = lambda_client.publish_layer_version(
                LayerName=layer_name,
                Description=f'Dependencies: {", ".join(packages)}',
                Content={'ZipFile': zip_data.read()},
                CompatibleRuntimes=['python3.13']
            )
        
        layer_arn = layer_response['LayerVersionArn']
        print(f"✅ Created Lambda layer: {layer_arn}")
        return layer_arn

# Generic Lambda function creator - packages code into ZIP and deploys

def create_lambda(name, code, lambda_role_arn, description, TAVILY_API_KEY=None, packages=None):

    """ Create Lambda layer if packages are specified """
    layer_arn = None
    if packages:
        layer_arn = create_lambda_layer(packages, f"{name}-layer")
            
    """Generic Lambda creator"""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        with zipfile.ZipFile(tmp_file.name, 'w') as zip_file:
            zip_file.writestr('lambda_function.py', code)
        with open(tmp_file.name, 'rb') as zip_data:
            lambda_zip = zip_data.read()
    
    try:
        if TAVILY_API_KEY:
            function_config = {
                'FunctionName': name,
                'Runtime': 'python3.13',
                'Role': lambda_role_arn,
                'Handler': 'lambda_function.lambda_handler',
                'Code': {'ZipFile': lambda_zip},
                'Description': description,
                'Timeout': 120,
                'MemorySize': 1024,
                'Environment': {
                    'Variables': {
                        'TAVILY_API_KEY': TAVILY_API_KEY
                    }
                }
            }
        else:
            function_config = {
                'FunctionName': name,
                'Runtime': 'python3.13',
                'Role': lambda_role_arn,
                'Handler': 'lambda_function.lambda_handler',
                'Code': {'ZipFile': lambda_zip},
                'Description': description,
                'Timeout': 120,
                'MemorySize': 1024                
            }

        # Add layer if created
        if layer_arn:
            function_config['Layers'] = [layer_arn]
            
        response = lambda_client.create_function(**function_config)
        
        return response['FunctionArn']
    except Exception as e:
        if "ResourceConflictException" in str(e):
            lambda_client.update_function_code(FunctionName=name, ZipFile=lambda_zip)
            return lambda_client.get_function(FunctionName=name)['Configuration']['FunctionArn']
        else:
            print(f"❌ Failed to create {name}: {str(e)}")
            raise e
        

