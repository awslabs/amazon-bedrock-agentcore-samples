import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export interface DatabaseStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
}

export class DatabaseStack extends cdk.Stack {
  public readonly tables: {
    [key: string]: dynamodb.Table;
  };

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    // Set parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Create DynamoDB tables for Bedrock agent chat functionality
    this.tables = {
      // Chat history table - stores conversation history
      chatHistory: new dynamodb.Table(this, 'ChatHistoryTable', {
        tableName: 'AgentCore-ChatHistory',
        partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'messageId', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
        pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      }),

      // Sessions table - stores user session information with user-level access control
      sessions: new dynamodb.Table(this, 'SessionsTable', {
        tableName: 'AgentCore-Sessions',
        partitionKey: { name: 'sessionId', type: dynamodb.AttributeType.STRING },
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
        pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      }),
    };

    // Add GSI to chat history table for querying by user
    this.tables.chatHistory.addGlobalSecondaryIndex({
      indexName: 'UserIdIndex',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Add GSI to sessions table for querying user sessions (for authorization)
    this.tables.sessions.addGlobalSecondaryIndex({
      indexName: 'UserIdIndex',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Store table names in SSM Parameter Store
    for (const [name, table] of Object.entries(this.tables)) {
      new ssm.StringParameter(this, `${name}TableNameParameter`, {
        parameterName: `${paramPrefix}/Tables/${name}TableName`,
        description: `${name} table name`,
        stringValue: table.tableName,
      });
    }

    // Outputs
    for (const [name, table] of Object.entries(this.tables)) {
      new cdk.CfnOutput(this, `${name}TableName`, {
        value: table.tableName,
        description: `${name} table name`,
        exportName: `${this.stackName}-${name}TableName`,
      });
    }

    // Tag all resources
    cdk.Tags.of(this).add('Project', 'AgentCoreTemplate');
  }
}
