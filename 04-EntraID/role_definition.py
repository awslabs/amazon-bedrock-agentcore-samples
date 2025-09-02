import boto3

def create_role(role_name, region, account_id):
    iam = boto3.client('iam')
    try:
        response = iam.get_role(RoleName=role_name)
        return response
    except:
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
        #trust_policy = json.loads(trust_policy.replace("accountId", account_id).replace("region", region))
        trust_policy = trust_policy.replace("accountId", account_id).replace("region", region)
        #permission = json.loads(permission.replace("accountId", account_id).replace("region", region))
        permission = permission.replace("accountId", account_id).replace("region", region)
    
        
        policy_name = role_name+"Policy"
        agentcore_iam_role = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=trust_policy
            )
        policy = iam.put_role_policy(
                PolicyDocument=permission,
                PolicyName="AgentCorePolicy",
                RoleName=role_name
            )
        return agentcore_iam_role