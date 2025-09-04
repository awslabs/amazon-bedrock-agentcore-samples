"""
AWS IAM Role Management Module

This module provides functionality to create IAM roles specifically configured
for AWS Bedrock AgentCore services with the necessary permissions and trust policies.
"""

import boto3
from botocore.exceptions import ClientError

def create_role(role_name, region, account_id):
    """
    Create an IAM role for Bedrock Agent Core with required permissions.
    
    Checks if the role already exists and returns it, otherwise creates a new role
    with comprehensive Bedrock Agent Core permissions including memory management,
    event handling, logging, ECR access, and model invocation capabilities.
    
    Args:
        role_name (str): Name of the IAM role to create or retrieve
        region (str): AWS region for the role configuration
        account_id (str): AWS account ID for resource ARN construction
        
    Returns:
        dict: IAM role response object containing role details
        
    Raises:
        ClientError: If role creation fails due to AWS API errors
    """
    iam = boto3.client('iam')
    try:
        response = iam.get_role(RoleName=role_name)
        return response
    except ClientError as e:
        print(f"Role {role_name} does not exist", e)
        permission = """{
            "Version": "2012-10-17",
            "Statement": [
                {
        			"Sid": "GetMemory",
        			"Effect": "Allow",
        			"Action": [
        				"bedrock-agentcore:GetMemory",
        				"bedrock-agentcore:ListMemoryRecords",
        				"bedrock-agentcore:RetrieveMemoryRecords",
        				"bedrock-agentcore:GetMemoryRecord",
        				"bedrock-agentcore:CreateMemory",
        				"bedrock-agentcore:DeleteMemory",
        				"bedrock-agentcore:DeleteMemoryRecord",
        				"bedrock-agentcore:UpdateMemory",
                        "bedrock-agentcore:DeleteAgentRuntime"
        			],
        			"Resource": "*"
        		},
        		{
        			"Sid": "CreateEvent",
        			"Effect": "Allow",
        			"Action": [
        				"bedrock-agentcore:CreateEvent"
        			],
        			"Resource": "*"
        		},
        		{
        			"Sid": "ListEvents",
        			"Effect": "Allow",
        			"Action": [
        				"bedrock-agentcore:ListEvents"
        			],
        			"Resource": "*"
        		},
                {
                    "Sid": "GetWorkloadAccessTokenForJWT",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "GetResourceOauth2Token",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetResourceOauth2Token"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "GetWorkloadAccessTokenForUserId",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "GetResourceAPIKey",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetResourceApiKey"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "SecretManager",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue"
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
                        "arn:aws:ecr:region:accountId:repository/*"
                    ]        
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogStreams",
                        "logs:CreateLogGroup"
                    ],
                    "Resource": [
                        "arn:aws:logs:region:accountId:log-group:/aws/bedrock-agentcore/runtimes/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogGroups"
                    ],
                    "Resource": [
                        "arn:aws:logs:region:accountId:log-group:*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": [
                        "arn:aws:logs:region:accountId:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
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
                      "arn:aws:bedrock-agentcore:region:accountId:workload-identity-directory/default",
                      "arn:aws:bedrock-agentcore:region:accountId:workload-identity-directory/default/workload-identity/agentName-*"
                    ]
                },
                 {"Sid": "BedrockModelInvocation", 
                 "Effect": "Allow", 
                 "Action": [ 
                        "bedrock:InvokeModel", 
                        "bedrock:InvokeModelWithResponseStream"
                      ], 
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:region:accountId:*"
                ]
                }
            ]
        }"""

        trust_policy = """{
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
                        "aws:SourceAccount": "accountId"
                    },
                    "ArnLike": {
                        "aws:SourceArn": "arn:aws:bedrock-agentcore:region:accountId:*"
                    }
               }
            }
          ]
        }"""
        trust_policy = trust_policy.replace("accountId", account_id).replace("region", region)
        permission = permission.replace("accountId", account_id).replace("region", region)


        policy_name = role_name+"Policy"
        agentcore_iam_role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=trust_policy
            )
        iam.put_role_policy(
                PolicyDocument=permission,
                PolicyName=policy_name,
                RoleName=role_name
            )
        return agentcore_iam_role
