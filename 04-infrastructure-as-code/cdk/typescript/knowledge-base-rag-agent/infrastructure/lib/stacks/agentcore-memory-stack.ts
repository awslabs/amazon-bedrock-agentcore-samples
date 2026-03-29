import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export interface AgentCoreMemoryStackProps extends cdk.StackProps {
  encryptionKey?: kms.IKey;
}

export class AgentCoreMemoryStack extends cdk.Stack {
  public readonly memory: agentcore.Memory;
  public readonly memoryIdParameter: ssm.StringParameter;

  constructor(scope: Construct, id: string, props?: AgentCoreMemoryStackProps) {
    super(scope, id, props);

    const paramPrefix = '/AgentCoreTemplate';

    // Import KMS key from storage stack if not provided
    let encryptionKey = props?.encryptionKey;
    if (!encryptionKey) {
      const encryptionKeyArn = ssm.StringParameter.valueForStringParameter(
        this,
        `${paramPrefix}/EncryptionKeyArn`
      );
      encryptionKey = kms.Key.fromKeyArn(this, 'ImportedEncryptionKey', encryptionKeyArn);
    }

    // Create AgentCore Memory with built-in strategies for long-term memory
    this.memory = new agentcore.Memory(this, 'AgentMemory', {
      memoryName: 'knowledge_base_rag_agent_memory',
      description: 'Memory store for Knowledge Base RAG Agent - supports conversation context and long-term recall',
      expirationDuration: cdk.Duration.days(90), // Short-term memory expires after 90 days
      kmsKey: encryptionKey,
      memoryStrategies: [
        // Semantic memory for extracting facts and concepts
        agentcore.MemoryStrategy.usingBuiltInSemantic(),
        // User preference memory for personalization
        agentcore.MemoryStrategy.usingBuiltInUserPreference(),
        // Summarization for conversation compression
        agentcore.MemoryStrategy.usingBuiltInSummarization(),
      ],
    });

    // Store memory ID in SSM Parameter Store
    this.memoryIdParameter = new ssm.StringParameter(this, 'MemoryIdParameter', {
      parameterName: `${paramPrefix}/AgentCore/MemoryId`,
      description: 'AgentCore Memory ID for Knowledge Base RAG Agent',
      stringValue: this.memory.memoryId,
    });

    // Outputs
    new cdk.CfnOutput(this, 'MemoryId', {
      value: this.memory.memoryId,
      description: 'AgentCore Memory ID',
      exportName: `${this.stackName}-MemoryId`,
    });

    new cdk.CfnOutput(this, 'MemoryArn', {
      value: this.memory.memoryArn,
      description: 'AgentCore Memory ARN',
      exportName: `${this.stackName}-MemoryArn`,
    });
  }
}
