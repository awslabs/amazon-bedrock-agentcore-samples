/**
 * CDK Stack for AgentCore Strands Data Analyst Assistant
 * 
 * Infrastructure for a data analyst assistant powered by Amazon Bedrock AgentCore.
 * Components:
 * - Aurora PostgreSQL database containing video games sales data
 * - DynamoDB tables for query results
 * - VPC with networking and security configuration
 * - IAM roles and permissions for AgentCore
 * - S3 bucket for data imports
 * - SSM parameters for configuration
 */

import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as iam from "aws-cdk-lib/aws-iam";
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export class CdkAgentcoreStrandsDataAnalystAssistantStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ================================
    // STACK PARAMETERS
    // ================================

    // Project identifier used in resource naming
    const projectId = new cdk.CfnParameter(this, "ProjectId", {
      type: "String",
      description: "Project identifier used for naming resources",
      default: "agentcore-data-analyst-assistant",
    });

    // Name of the Aurora PostgreSQL database
    const databaseName = new cdk.CfnParameter(this, "DatabaseName", {
      type: "String",
      description: "The database name",
      default: "video_games_sales",
    });

    // ================================
    // DYNAMODB TABLES
    // ================================

    // DynamoDB table containing SQL query results from the agent
    const rawQueryResults = new dynamodb.Table(this, "RawQueryResults", {
      partitionKey: {
        name: "id",
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: "my_timestamp",
        type: dynamodb.AttributeType.NUMBER,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    // ================================
    // VPC AND NETWORKING
    // ================================

    // VPC containing public and private subnets for secure database access
    const vpc = new ec2.Vpc(this, "AssistantVPC", {
      vpcName: `${projectId.valueAsString}-vpc`,
      ipAddresses: ec2.IpAddresses.cidr("10.0.0.0/21"),
      maxAzs: 3,
      natGateways: 1,
      subnetConfiguration: [
        {
          subnetType: ec2.SubnetType.PUBLIC,
          name: "Ingress",
          cidrMask: 24,
        },
        {
          cidrMask: 24,
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Gateway endpoints providing cost-effective access to AWS services
    vpc.addGatewayEndpoint("S3Endpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
      subnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
    });

    vpc.addGatewayEndpoint("DynamoDBEndpoint", {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
      subnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
    });

    // ================================
    // DATABASE INFRASTRUCTURE
    // ================================

    // Security group controlling access to Aurora PostgreSQL cluster (via RDS Data API)
    const sg_db = new ec2.SecurityGroup(
      this,
      "AssistantDBSecurityGroup",
      {
        vpc: vpc,
        allowAllOutbound: true,
        description: "Security group for Aurora PostgreSQL cluster accessed via RDS Data API"
      }
    );

    // Database credentials stored in AWS Secrets Manager
    const databaseUsername = "postgres";
    const secret = new rds.DatabaseSecret(this, "AssistantSecret", {
      username: databaseUsername,
      secretName: `${projectId.valueAsString}-db-secret`,
    });

    // IAM role enabling Aurora S3 access for data imports
    const auroraS3Role = new iam.Role(this, "AuroraS3Role", {
      assumedBy: new iam.ServicePrincipal("rds.amazonaws.com"),
    });

    // Aurora PostgreSQL Serverless v2 cluster containing video games sales data
    let cluster = new rds.DatabaseCluster(this, "AssistantCluster", {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_17_4,
      }),
      writer: rds.ClusterInstance.serverlessV2("writer"),
      serverlessV2MinCapacity: 2,
      serverlessV2MaxCapacity: 4,
      defaultDatabaseName: databaseName.valueAsString,
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [sg_db],
      credentials: rds.Credentials.fromSecret(secret),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      enableDataApi: true,
      s3ImportRole: auroraS3Role,
      storageEncrypted: true, // Ensure storage encryption
    });

    // ================================
    // AGENTCORE IAM ROLE & PERMISSIONS
    // ================================

    // IAM role with comprehensive permissions for Amazon Bedrock AgentCore
    const agentCoreRole = new iam.Role(this, 'AgentCoreMyRole', {
      roleName: `AgentCoreExecution-${projectId.valueAsString}-${this.region}`,
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      inlinePolicies: {
        'AgentCoreExecutionPolicy': new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'ECRImageAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'ecr:BatchCheckLayerAvailability',
                'ecr:BatchGetImage',
                'ecr:GetDownloadUrlForLayer',
                'ecr:PutImage',
                'ecr:InitiateLayerUpload',
                'ecr:UploadLayerPart',
                'ecr:CompleteLayerUpload',
              ],
              resources: [
                `arn:aws:ecr:${this.region}:${this.account}:repository/*`
              ]
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:DescribeLogStreams',
                'logs:CreateLogGroup'
              ],
              resources: [
                `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`
              ]
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:DescribeLogGroups'
              ],
              resources: [
                `arn:aws:logs:${this.region}:${this.account}:log-group:*`
              ]
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'logs:CreateLogStream',
                'logs:PutLogEvents'
              ],
              resources: [
                `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`
              ]
            }),
            new iam.PolicyStatement({
              sid: 'ECRTokenAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'ecr:GetAuthorizationToken'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
                'xray:GetSamplingRules',
                'xray:GetSamplingTargets'
              ],
              resources: ['*']
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['cloudwatch:PutMetricData'],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cloudwatch:namespace': 'bedrock-agentcore'
                }
              }
            }),
            new iam.PolicyStatement({
              sid: 'GetAgentAccessToken',
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:GetWorkloadAccessToken',
                'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
                'bedrock-agentcore:GetWorkloadAccessTokenForUserId'
              ],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/*`
              ]
            }),
            new iam.PolicyStatement({
              sid: 'BedrockModelInvocation',
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream'
              ],
              resources: [
                'arn:aws:bedrock:*::foundation-model/*',
                `arn:aws:bedrock:${this.region}:${this.account}:*`
              ]
            }),
            // New permissions for RDS Data API
            new iam.PolicyStatement({
              sid: 'RDSDataAPIAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'rds-data:ExecuteStatement',
                'rds-data:BatchExecuteStatement'
              ],
              resources: [
                cluster.clusterArn
              ]
            }),
            // New permissions for Secrets Manager
            new iam.PolicyStatement({
              sid: 'SecretsManagerAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'secretsmanager:GetSecretValue'
              ],
              resources: [
                secret.secretArn
              ]
            }),
            // New permissions for SSM Parameter Store
            new iam.PolicyStatement({
              sid: 'SSMParameterAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'ssm:GetParameter',
                'ssm:GetParameters'
              ],
              resources: [
                `arn:aws:ssm:${this.region}:${this.account}:parameter/${projectId.valueAsString}/*`
              ]
            }),
            // Permissions for DynamoDB
            new iam.PolicyStatement({
              sid: 'DynamoDBTableAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'dynamodb:Query',
                'dynamodb:Scan',
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem'
              ],
              resources: [
                rawQueryResults.tableArn
              ]
            }),
            // Permissions for AgentCore Memory
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreMemoryAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:GetMemoryRecord',
                'bedrock-agentcore:GetMemory',
                'bedrock-agentcore:RetrieveMemoryRecords',
                'bedrock-agentcore:DeleteMemoryRecord',
                'bedrock-agentcore:ListMemoryRecords',
                'bedrock-agentcore:CreateEvent',
                'bedrock-agentcore:ListSessions',
                'bedrock-agentcore:ListEvents',
                'bedrock-agentcore:GetEvent'
              ],
              resources: [
                `*`
              ]
            }),
            new iam.PolicyStatement({
              sid: 'BedrockModelInvocationMemory',
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream'
              ],
              resources: [
                'arn:aws:bedrock:*::foundation-model/*',
                'arn:aws:bedrock:*:*:inference-profile/*'
              ]
            }),
          ]
        })
      }
    });

    // Add the specific trust relationship with sts:TagSession permission
    (agentCoreRole.node.defaultChild as iam.CfnRole).addPropertyOverride(
      'AssumeRolePolicyDocument',
      {
        Version: '2012-10-17',
        Statement: [
          {
            Sid: 'Statement1',
            Effect: 'Allow',
            Principal: {
              Service: 'bedrock-agentcore.amazonaws.com'
            },
            Action: [
              'sts:AssumeRole',
              'sts:TagSession'
            ]
          }
        ]
      }
    );

    // Grant S3 access to the role
    auroraS3Role.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
        resources: [
          `arn:aws:s3:::${projectId.valueAsString}-${this.region}-${this.account}-import`,
          `arn:aws:s3:::${projectId.valueAsString}-${this.region}-${this.account}-import/*`,
        ],
      })
    );

    // Add additional RDS permissions
    auroraS3Role.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "rds:CreateDBSnapshot",
          "rds:CreateDBClusterSnapshot",
          "rds:RestoreDBClusterFromSnapshot",
          "rds:RestoreDBClusterToPointInTime",
          "rds:RestoreDBInstanceFromDBSnapshot",
          "rds:RestoreDBInstanceToPointInTime",
        ],
        resources: [cluster.clusterArn],
      })
    );

    // ================================
    // S3 STORAGE
    // ================================

    // S3 bucket containing data for import into Aurora PostgreSQL
    const importBucket = new s3.Bucket(this, "ImportBucket", {
      bucketName: `${projectId.valueAsString}-${this.region}-${this.account}-import`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(7), // Auto-delete objects after 7 days
        },
      ],
    });

    // ================================
    // SSM PARAMETERS
    // ================================

    // SSM parameters containing AgentCore runtime configuration
    new ssm.CfnParameter(this, 'SecretArnParam', {
      name: `/${projectId.valueAsString}/SECRET_ARN`,
      value: secret.secretArn,
      description: 'Database secret ARN',
      type: 'String'
    });

    new ssm.CfnParameter(this, 'AuroraResourceArnParam', {
      name: `/${projectId.valueAsString}/AURORA_RESOURCE_ARN`,
      value: cluster.clusterArn,
      description: 'Aurora cluster ARN',
      type: 'String'
    });

    new ssm.CfnParameter(this, 'DatabaseNameParam', {
      name: `/${projectId.valueAsString}/DATABASE_NAME`,
      value: databaseName.valueAsString,
      description: 'Database name',
      type: 'String'
    });

    new ssm.CfnParameter(this, 'QuestionAnswersTableParam', {
      name: `/${projectId.valueAsString}/QUESTION_ANSWERS_TABLE`,
      value: rawQueryResults.tableName,
      description: 'DynamoDB question answers table name',
      type: 'String'
    });

    new ssm.CfnParameter(this, 'MaxResponseSizeBytesParam', {
      name: `/${projectId.valueAsString}/MAX_RESPONSE_SIZE_BYTES`,
      value: '1048576',
      description: 'Maximum response size in bytes (1MB)',
      type: 'String'
    });

    new ssm.CfnParameter(this, 'MemoryIdParam', {
      name: `/${projectId.valueAsString}/MEMORY_ID`,
      value: "AssistantAgentMemoryIdToBeCreated",
      description: 'Memory ID for the agent',
      type: 'String'
    });

    // ================================
    // CLOUDFORMATION OUTPUTS
    // ================================

    // Aurora database cluster ARN
    new cdk.CfnOutput(this, "AuroraServerlessDBClusterARN", {
      value: cluster.clusterArn,
      description: "The ARN of the Aurora Serverless DB Cluster",
      exportName: `${projectId.valueAsString}-AuroraServerlessDBClusterARN`,
    });

    new cdk.CfnOutput(this, "SecretARN", {
      value: secret.secretArn,
      description: "The ARN of the database credentials secret",
      exportName: `${projectId.valueAsString}-SecretArn`,
    });

    new cdk.CfnOutput(this, "DataSourceBucketName", {
      value: importBucket.bucketName,
      description:
        "S3 bucket for importing data into Aurora using aws_s3 extension",
      exportName: `${projectId.valueAsString}-ImportBucketName`,
    });

    new cdk.CfnOutput(this, "QuestionAnswersTableName", {
      value: rawQueryResults.tableName,
      description: "The name of the DynamoDB table for storing query results",
      exportName: `${projectId.valueAsString}-QuestionAnswersTableName`,
    });

    new cdk.CfnOutput(this, "AgentCoreMyRoleARN", {
      value: agentCoreRole.roleArn,
      description: "The ARN of the AgentCoreMyRole",
      exportName: `${projectId.valueAsString}-AgentCoreMyRoleARN`,
    });

    new cdk.CfnOutput(this, "MemoryIdSSMParameter", {
      value: `/${projectId.valueAsString}/MEMORY_ID`,
      description: "The SSM parameter name for the memory ID",
      exportName: `${projectId.valueAsString}-MemoryIdSSMParameter`,
    });


  }
}
