import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export interface NetworkStackProps extends cdk.StackProps {
  cidr?: string;
  maxAzs?: number;
}

export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly securityGroups: {
    [key: string]: ec2.SecurityGroup;
  };
  public readonly logGroup: logs.LogGroup;

  constructor(scope: Construct, id: string, props?: NetworkStackProps) {
    super(scope, id, props);

    // Parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Create VPC with standard configuration
    this.vpc = new ec2.Vpc(this, 'VPC', {
      ipAddresses: ec2.IpAddresses.cidr(props?.cidr || '10.0.0.0/18'),
      maxAzs: props?.maxAzs || 2,
      vpcName: 'bedrock-agent-vpc',
      subnetConfiguration: [
        {
          name: 'public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
        {
          name: 'isolated',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
      natGateways: 1, // Single NAT gateway for cost optimization
    });

    // Create security groups
    this.securityGroups = {
      // API security group
      api: new ec2.SecurityGroup(this, 'ApiSecurityGroup', {
        vpc: this.vpc,
        description: 'Security group for API',
        allowAllOutbound: true,
        securityGroupName: 'bedrock-agent-api-sg',
      }),

      // Database security group
      database: new ec2.SecurityGroup(this, 'DatabaseSecurityGroup', {
        vpc: this.vpc,
        description: 'Security group for database',
        allowAllOutbound: false,
        securityGroupName: 'bedrock-agent-db-sg',
      }),

      // Service security group
      service: new ec2.SecurityGroup(this, 'ServiceSecurityGroup', {
        vpc: this.vpc,
        description: 'Security group for services',
        allowAllOutbound: true,
        securityGroupName: 'bedrock-agent-service-sg',
      }),
    };

    // Allow API to access services
    this.securityGroups.service.connections.allowFrom(
      this.securityGroups.api,
      ec2.Port.tcp(80),
      'Allow API to access services'
    );

    // Allow services to access database
    this.securityGroups.database.connections.allowFrom(
      this.securityGroups.service,
      ec2.Port.tcp(5432),
      'Allow services to access database'
    );

    // Create CloudWatch log group
    this.logGroup = new logs.LogGroup(this, 'LogGroup', {
      logGroupName: '/aws/knowledge-base-rag-agent',
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Store VPC ID in SSM Parameter Store
    new ssm.StringParameter(this, 'VpcIdParameter', {
      parameterName: `${paramPrefix}/VpcId`,
      description: 'VPC ID',
      stringValue: this.vpc.vpcId,
    });

    // Store security group IDs in SSM Parameter Store
    new ssm.StringParameter(this, 'ApiSecurityGroupIdParameter', {
      parameterName: `${paramPrefix}/ApiSecurityGroupId`,
      description: 'API Security Group ID',
      stringValue: this.securityGroups.api.securityGroupId,
    });

    new ssm.StringParameter(this, 'DatabaseSecurityGroupIdParameter', {
      parameterName: `${paramPrefix}/DatabaseSecurityGroupId`,
      description: 'Database Security Group ID',
      stringValue: this.securityGroups.database.securityGroupId,
    });

    new ssm.StringParameter(this, 'ServiceSecurityGroupIdParameter', {
      parameterName: `${paramPrefix}/ServiceSecurityGroupId`,
      description: 'Service Security Group ID',
      stringValue: this.securityGroups.service.securityGroupId,
    });

    // Store log group name in SSM Parameter Store
    new ssm.StringParameter(this, 'LogGroupNameParameter', {
      parameterName: `${paramPrefix}/LogGroupName`,
      description: 'Log Group Name',
      stringValue: this.logGroup.logGroupName,
    });

    // Outputs
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'VPC ID',
      exportName: `${this.stackName}-VpcId`,
    });

    new cdk.CfnOutput(this, 'LogGroupName', {
      value: this.logGroup.logGroupName,
      description: 'Log Group Name',
      exportName: `${this.stackName}-LogGroupName`,
    });
  }
}
