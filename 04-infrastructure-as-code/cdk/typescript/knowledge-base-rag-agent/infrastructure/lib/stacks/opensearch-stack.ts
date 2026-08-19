import * as cdk from 'aws-cdk-lib';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as path from 'path';
import { Construct } from 'constructs';

/**
 * Properties for the OpenSearch Serverless Stack
 * This stack creates the vector database infrastructure needed for the Bedrock Knowledge Base
 */
export interface OpenSearchStackProps extends cdk.StackProps {
  /** The name of the OpenSearch Serverless collection for vector storage */
  collectionName: string;
  /** The name of the vector index within the collection */
  vectorIndexName: string;
  /** The name of the IAM role that Bedrock will use to access OpenSearch */
  bedrockRoleName: string;
  /** The name of the Bedrock Knowledge Base */
  knowledgeBaseName?: string;
}

/**
 * AWS CDK Stack for OpenSearch Serverless Vector Database
 *
 * This stack creates the vector storage infrastructure required for Bedrock Knowledge Base:
 * - OpenSearch Serverless collection optimized for vector search
 * - Security policies for encryption and network access
 * - IAM role for Bedrock to access the collection
 * - Vector index for storing document embeddings
 *
 * OpenSearch Serverless provides automatic scaling and management of the vector database,
 * making it ideal for AI/ML workloads that need semantic search capabilities.
 */
export class OpenSearchStack extends cdk.Stack {
  /** The ARN of the OpenSearch Serverless collection */
  public readonly collectionArn: string;
  /** The unique ID of the OpenSearch collection */
  public readonly collectionId: string;
  /** The HTTPS endpoint for accessing the collection */
  public readonly collectionEndpoint: string;
  /** The name of the vector index for document embeddings */
  public readonly vectorIndexName: string;
  /** The IAM role that allows Bedrock to access this OpenSearch collection */
  public readonly bedrockRole: iam.Role;
  /** The S3 bucket for knowledge base documents */
  public readonly knowledgeBaseBucket: s3.Bucket;
  /** The Bedrock Knowledge Base ID */
  public readonly knowledgeBaseId: string;
  /** The Bedrock Data Source ID */
  public readonly dataSourceId: string;

  constructor(scope: Construct, id: string, props: OpenSearchStackProps) {
    super(scope, id, props);

    // Use consistent parameter naming without environment complexity

    // Create IAM role for Bedrock to access OpenSearch Serverless
    // This role allows Bedrock services to read/write vector data and manage the collection
    this.bedrockRole = new iam.Role(this, 'BedrockKnowledgeBaseRole', {
      roleName: props.bedrockRoleName,
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'IAM role for Bedrock to access OpenSearch Serverless',
    });

    // Create encryption policy for the OpenSearch collection
    // This ensures all data is encrypted at rest using AWS-managed keys
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: `br-encrypt-${props.collectionName.substring(0, 20)}`,
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [
          {
            ResourceType: 'collection',
            Resource: [`collection/${props.collectionName}`],
          },
        ],
        AWSOwnedKey: true, // Use AWS-managed encryption keys for simplicity
      }),
    });

    // Create network policy to control access to the collection
    // This allows public access which is needed for Bedrock integration
    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: `br-network-${props.collectionName.substring(0, 20)}`,
      type: 'network',
      policy: JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'collection',
              Resource: [`collection/${props.collectionName}`],
            },
            {
              ResourceType: 'dashboard',
              Resource: [`collection/${props.collectionName}`],
            },
          ],
          AllowFromPublic: true, // Required for Bedrock service access
        },
      ]),
    });

    // We'll create the data access policy after the Lambda function is created
    // to include its role in the policy

    // Create the OpenSearch Serverless collection for vector search
    // This collection will store document embeddings for semantic search
    const collection = new opensearchserverless.CfnCollection(this, 'Collection', {
      name: props.collectionName,
      type: 'VECTORSEARCH', // Optimized for vector/embedding storage and search
      description: 'Vector search collection for Bedrock Knowledge Base',
    });

    // Ensure security policies are created before the collection
    // This prevents permission errors during collection creation
    collection.addDependency(encryptionPolicy);
    collection.addDependency(networkPolicy);

    // Store collection details for use by other stacks
    this.collectionArn = collection.attrArn;
    this.collectionId = collection.attrId;
    this.collectionEndpoint = collection.attrCollectionEndpoint;
    this.vectorIndexName = props.vectorIndexName;

    // Create a Lambda function to set up the vector index in OpenSearch
    // This is needed because CDK doesn't natively support creating vector indices
    // The function creates the index with the proper mapping for vector embeddings

    // Import the common layer from the shared resources stack
    const commonLayerArn = ssm.StringParameter.valueForStringParameter(
      this,
      '/AgentCoreTemplate/CommonLayerArn'
    );
    const commonLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'CommonLayer',
      commonLayerArn
    );

    const createVectorIndexFunction = new lambda.Function(this, 'CreateVectorIndexFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.resolve(__dirname, '../../src/functions/vector-index')),
      layers: [commonLayer],
      timeout: cdk.Duration.minutes(10),
      environment: {
        COLLECTION_NAME: props.collectionName,
        VECTOR_INDEX_NAME: props.vectorIndexName,
      },
      description: 'Creates vector index in OpenSearch Serverless collection',
      // T-3 DoS Protection: Set reserved concurrency for setup function (lower limit as it's used less frequently)
      reservedConcurrentExecutions: 5, // Lower limit for setup/configuration function
    });

    // Grant the Lambda function permissions to manage OpenSearch Serverless
    // This allows the function to create and configure the vector index
    createVectorIndexFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'aoss:*',
        ],
        resources: ['*'], // OpenSearch Serverless doesn't support resource-specific ARNs
      })
    );

    // Grant KMS permissions for encrypted OpenSearch collections
    // Even with AWS-managed keys, Lambda needs these permissions to work with encrypted collections
    createVectorIndexFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'kms:Decrypt',
          'kms:DescribeKey',
          'kms:GenerateDataKey',
        ],
        resources: [
          // AWS-managed key for OpenSearch Serverless
          `arn:aws:kms:${this.region}:${this.account}:key/*`,
        ],
        conditions: {
          StringEquals: {
            'kms:ViaService': `aoss.${this.region}.amazonaws.com`,
          },
        },
      })
    );

    // Create comprehensive data access policy that includes all necessary principals
    // This grants the Bedrock role, Lambda function, and account root the necessary permissions
    // Note: This policy must be created after the Lambda function to avoid circular dependencies
    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'DataAccessPolicy', {
      name: `br-access-${props.collectionName.substring(0, 20)}`,
      type: 'data',
      policy: JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'collection',
              Resource: [`collection/${props.collectionName}`],
              Permission: [
                'aoss:CreateCollectionItems',
                'aoss:DeleteCollectionItems',
                'aoss:UpdateCollectionItems',
                'aoss:DescribeCollectionItems',
              ],
            },
            {
              ResourceType: 'index',
              Resource: [`index/${props.collectionName}/*`],
              Permission: [
                'aoss:CreateIndex',
                'aoss:DeleteIndex',
                'aoss:UpdateIndex',
                'aoss:DescribeIndex',
                'aoss:ReadDocument',
                'aoss:WriteDocument',
              ],
            },
          ],
          // Grant access to Bedrock role, Lambda function, and account root
          Principal: [
            this.bedrockRole.roleArn,
            createVectorIndexFunction.role!.roleArn,
            `arn:aws:iam::${this.account}:root`,
          ],
        },
      ]),
    });

    // Create custom resource to set up the vector index
    // This runs the Lambda function to create the index with proper vector mappings
    const createVectorIndex = new cdk.CustomResource(this, 'CreateVectorIndex', {
      serviceToken: new cr.Provider(this, 'CreateVectorIndexProvider', {
        onEventHandler: createVectorIndexFunction,
      }).serviceToken,
      properties: {
        CollectionId: props.collectionName,
        IndexName: props.vectorIndexName,
        ResourceId: `VectorIndex-${props.collectionName}-${props.vectorIndexName}`,
        Version: '5.0', // Increment this to force re-execution of the custom resource
      },
    });

    // Ensure proper resource creation order
    // Ensure proper resource creation order to avoid circular dependencies:
    // 1. Collection (depends on encryption/network policies)
    // 2. Lambda function (independent)
    // 3. Data access policy (depends on collection and references Lambda role)
    // 4. Custom resource (depends on collection and data access policy)
    dataAccessPolicy.node.addDependency(collection);
    dataAccessPolicy.node.addDependency(createVectorIndexFunction);
    createVectorIndex.node.addDependency(collection);
    createVectorIndex.node.addDependency(dataAccessPolicy);

    // Grant Bedrock comprehensive permissions to work with OpenSearch and related services
    // This policy allows Bedrock to read/write vectors and invoke foundation models
    this.bedrockRole.attachInlinePolicy(
      new iam.Policy(this, 'BedrockOpenSearchPolicy', {
        statements: [
          // OpenSearch Serverless permissions for vector operations
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'aoss:APIAccessAll', // Full API access to the collection (covers all data plane operations)
            ],
            resources: [this.collectionArn],
          }),
          // Bedrock foundation model access for embeddings and generation
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'bedrock:InvokeModel',
              'bedrock:InvokeModelWithResponseStream'
            ],
            resources: [
              // Direct foundation model access - use wildcard for all regions
              // Cross-region inference profiles can route to any region for availability
              `arn:aws:bedrock:*::foundation-model/*`,
              // Cross-region inference profile access (for us.anthropic.claude-sonnet-4-* models)
              `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
              // Application inference profile access
              `arn:aws:bedrock:${this.region}:${this.account}:application-inference-profile/*`
            ],
          }),
          // Knowledge base operations
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: ['bedrock:Retrieve', 'bedrock:RetrieveAndGenerate'],
            resources: [`arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/*`],
          }),
          // S3 access for knowledge base documents (using wildcard for flexibility)
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: ['s3:GetObject', 's3:ListBucket'],
            resources: [
              'arn:aws:s3:::*-knowledgebasebucket*',
              'arn:aws:s3:::*-knowledgebasebucket*/*',
            ],
          }),
          // KMS permissions for S3 encryption/decryption
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'kms:Decrypt',
              'kms:DescribeKey',
              'kms:GenerateDataKey',
            ],
            resources: [
              // Allow access to the S3 encryption key
              `arn:aws:kms:${this.region}:${this.account}:key/*`,
            ],
            conditions: {
              StringEquals: {
                'kms:ViaService': [`s3.${this.region}.amazonaws.com`],
              },
            },
          }),
        ],
      })
    );

    // ========================================================================
    // KNOWLEDGE BASE RESOURCES
    // ========================================================================

    // Create S3 bucket for knowledge base documents
    this.knowledgeBaseBucket = new s3.Bucket(this, 'KnowledgeBaseBucket', {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For dev/demo - use RETAIN for production
      autoDeleteObjects: true, // For dev/demo - remove for production
      enforceSSL: true,
    });

    // Grant Bedrock role access to the knowledge base bucket
    this.knowledgeBaseBucket.grantRead(this.bedrockRole);

    // Create Bedrock Knowledge Base with OpenSearch Serverless storage
    const knowledgeBaseName = props.knowledgeBaseName || 'AgentCoreKnowledgeBase';
    const knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', {
      name: knowledgeBaseName,
      description: 'Knowledge base for AgentCore Template with OpenSearch Serverless vector storage',
      roleArn: this.bedrockRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          // Using v2 with 1024-dimension vectors (better multilingual support, 100+ languages)
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: this.collectionArn,
          vectorIndexName: this.vectorIndexName,
          fieldMapping: {
            vectorField: 'vector',
            textField: 'text',
            metadataField: '_metadata',
          },
        },
      },
    });

    // Ensure Knowledge Base is created after the vector index
    knowledgeBase.node.addDependency(createVectorIndex);

    // Store Knowledge Base ID
    this.knowledgeBaseId = knowledgeBase.attrKnowledgeBaseId;

    // Create S3 Data Source for the Knowledge Base
    const dataSource = new bedrock.CfnDataSource(this, 'KnowledgeBaseDataSource', {
      knowledgeBaseId: this.knowledgeBaseId,
      name: 'S3DataSource',
      description: 'S3 data source for knowledge base documents',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.knowledgeBaseBucket.bucketArn,
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: {
            maxTokens: 512,
            overlapPercentage: 20,
          },
        },
      },
    });

    // Store Data Source ID
    this.dataSourceId = dataSource.attrDataSourceId;

    // ========================================================================
    // SSM PARAMETERS
    // ========================================================================

    // Store OpenSearch details in SSM Parameter Store for other stacks to reference
    // This enables loose coupling between the OpenSearch and Bedrock stacks
    new ssm.StringParameter(this, 'CollectionArnParameter', {
      parameterName: '/AgentCoreTemplate/OpenSearch/CollectionArn',
      stringValue: this.collectionArn,
      description: 'OpenSearch Serverless collection ARN',
    });

    new ssm.StringParameter(this, 'VectorIndexNameParameter', {
      parameterName: '/AgentCoreTemplate/OpenSearch/VectorIndexName',
      stringValue: this.vectorIndexName,
      description: 'Vector index name for embeddings',
    });

    new ssm.StringParameter(this, 'BedrockRoleArnParameter', {
      parameterName: '/AgentCoreTemplate/OpenSearch/BedrockRoleArn',
      stringValue: this.bedrockRole.roleArn,
      description: 'IAM role ARN for Bedrock access',
    });

    new ssm.StringParameter(this, 'CollectionEndpointParameter', {
      parameterName: '/AgentCoreTemplate/OpenSearch/CollectionEndpoint',
      stringValue: this.collectionEndpoint,
      description: 'OpenSearch Serverless collection endpoint',
    });

    // Knowledge Base SSM Parameters
    new ssm.StringParameter(this, 'KnowledgeBaseBucketParameter', {
      parameterName: '/AgentCoreTemplate/KnowledgeBaseBucket',
      stringValue: this.knowledgeBaseBucket.bucketName,
      description: 'S3 bucket for knowledge base documents',
    });

    new ssm.StringParameter(this, 'KnowledgeBaseIdParameter', {
      parameterName: '/AgentCoreTemplate/KnowledgeBaseId',
      stringValue: this.knowledgeBaseId,
      description: 'Bedrock Knowledge Base ID',
    });

    new ssm.StringParameter(this, 'DataSourceIdParameter', {
      parameterName: '/AgentCoreTemplate/DataSourceId',
      stringValue: this.dataSourceId,
      description: 'Bedrock Knowledge Base Data Source ID',
    });

    // CloudFormation outputs for easy reference after deployment
    new cdk.CfnOutput(this, 'CollectionArn', {
      value: this.collectionArn,
      description: 'OpenSearch Serverless collection ARN',
      exportName: `${this.stackName}-CollectionArn`,
    });

    new cdk.CfnOutput(this, 'CollectionEndpoint', {
      value: this.collectionEndpoint,
      description: 'OpenSearch Serverless collection endpoint',
      exportName: `${this.stackName}-CollectionEndpoint`,
    });

    new cdk.CfnOutput(this, 'VectorIndexName', {
      value: this.vectorIndexName,
      description: 'Name of the vector index for embeddings',
      exportName: `${this.stackName}-VectorIndexName`,
    });

    new cdk.CfnOutput(this, 'BedrockRoleArn', {
      value: this.bedrockRole.roleArn,
      description: 'IAM role ARN for Bedrock services',
      exportName: `${this.stackName}-BedrockRoleArn`,
    });

    // Knowledge Base CloudFormation Outputs (required by upload-documents.sh script)
    new cdk.CfnOutput(this, 'KnowledgeBaseBucketName', {
      value: this.knowledgeBaseBucket.bucketName,
      description: 'S3 bucket for knowledge base documents',
      exportName: `${this.stackName}-KnowledgeBaseBucketName`,
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: this.knowledgeBaseId,
      description: 'Bedrock Knowledge Base ID',
      exportName: `${this.stackName}-KnowledgeBaseId`,
    });

    new cdk.CfnOutput(this, 'DataSourceId', {
      value: this.dataSourceId,
      description: 'Bedrock Knowledge Base Data Source ID',
      exportName: `${this.stackName}-DataSourceId`,
    });

    // Tag all resources for organization and cost tracking
    cdk.Tags.of(this).add('Project', 'AgentCore');
  }
}
