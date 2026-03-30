import * as path from 'path';
import * as fs from 'fs';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { NagSuppressions } from 'cdk-nag';

interface Config {
  agentDescription: string;
  agentInstruction: string;
  agentModelId: string;
  tikaImageTag: string;
  fargateMemoryMiB: number;
  fargateCpu: number;
  desiredCount: number;
}

export class DigitalPreservationStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const configPath = path.join(__dirname, '../../config.json');
    const config: Config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    const projectRoot = path.join(__dirname, '../../..');

    // --- VPC ---
    const vpc = new ec2.Vpc(this, 'Vpc', { maxAzs: 2, natGateways: 1 });

    const vpcFlowLogGroup = new logs.LogGroup(this, 'VpcFlowLogGroup', {
      retention: logs.RetentionDays.ONE_WEEK,
    });
    vpc.addFlowLog('FlowLog', {
      destination: ec2.FlowLogDestination.toCloudWatchLogs(vpcFlowLogGroup),
    });
    vpc.addGatewayEndpoint('S3Endpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    // --- ECS Cluster ---
    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc,
      containerInsightsV2: ecs.ContainerInsights.ENABLED,
    });

    // --- Tika Fargate Service ---
    const tikaTaskDef = new ecs.FargateTaskDefinition(this, 'TikaTaskDef', {
      memoryLimitMiB: config.fargateMemoryMiB,
      cpu: config.fargateCpu,
    });
    tikaTaskDef.addContainer('tika', {
      image: ecs.ContainerImage.fromRegistry(`apache/tika:${config.tikaImageTag}`),
      portMappings: [{ containerPort: 9998 }],
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'tika', logRetention: logs.RetentionDays.ONE_WEEK }),
    });
    const tikaService = new ecs.FargateService(this, 'TikaService', {
      cluster, taskDefinition: tikaTaskDef, desiredCount: config.desiredCount,
      assignPublicIp: false, vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    // --- Siegfried Fargate Service ---
    const siegfriedTaskDef = new ecs.FargateTaskDefinition(this, 'SiegfriedTaskDef', {
      memoryLimitMiB: config.fargateMemoryMiB,
      cpu: config.fargateCpu,
    });
    siegfriedTaskDef.addContainer('siegfried', {
      image: ecs.ContainerImage.fromRegistry('ghcr.io/keeps/siegfried:v1.10.1'),
      portMappings: [{ containerPort: 5138 }],
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'siegfried', logRetention: logs.RetentionDays.ONE_WEEK }),
    });
    const siegfriedService = new ecs.FargateService(this, 'SiegfriedService', {
      cluster, taskDefinition: siegfriedTaskDef, desiredCount: config.desiredCount,
      assignPublicIp: false, vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    // --- DROID Fargate Service ---
    const droidTaskDef = new ecs.FargateTaskDefinition(this, 'DroidTaskDef', {
      memoryLimitMiB: config.fargateMemoryMiB,
      cpu: config.fargateCpu,
    });
    droidTaskDef.addContainer('droid', {
      image: ecs.ContainerImage.fromAsset(path.join(projectRoot, 'containers/droid'), {
        platform: ecr_assets.Platform.LINUX_AMD64,
      }),
      portMappings: [{ containerPort: 8080 }],
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'droid', logRetention: logs.RetentionDays.ONE_WEEK }),
    });
    const droidService = new ecs.FargateService(this, 'DroidService', {
      cluster, taskDefinition: droidTaskDef, desiredCount: config.desiredCount,
      assignPublicIp: false, vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    // --- MediaInfo Fargate Service ---
    const mediainfoTaskDef = new ecs.FargateTaskDefinition(this, 'MediaInfoTaskDef', {
      memoryLimitMiB: config.fargateMemoryMiB,
      cpu: config.fargateCpu,
    });
    mediainfoTaskDef.addContainer('mediainfo', {
      image: ecs.ContainerImage.fromAsset(path.join(projectRoot, 'containers/mediainfo'), {
        platform: ecr_assets.Platform.LINUX_AMD64,
      }),
      portMappings: [{ containerPort: 8081 }],
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'mediainfo', logRetention: logs.RetentionDays.ONE_WEEK }),
    });
    const mediainfoService = new ecs.FargateService(this, 'MediaInfoService', {
      cluster, taskDefinition: mediainfoTaskDef, desiredCount: config.desiredCount,
      assignPublicIp: false, vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    // --- S3 Buckets ---
    const accessLogsBucket = new s3.Bucket(this, 'AccessLogsBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
    });

    const docsBucket = new s3.Bucket(this, 'DocsBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 's3-access-logs/',
    });

    // --- Internal ALB with path-based routing ---
    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      vpc, internetFacing: false,
    });
    alb.logAccessLogs(accessLogsBucket, 'alb-logs');

    // Restrict ALB SG to VPC CIDR
    const albSg = alb.connections.securityGroups[0];
    const cfnSg = albSg.node.defaultChild as ec2.CfnSecurityGroup;
    cfnSg.addPropertyOverride('SecurityGroupIngress', [
      { IpProtocol: 'tcp', FromPort: 80, ToPort: 80, CidrIp: vpc.vpcCidrBlock, Description: 'Allow HTTP from VPC' },
    ]);

    const listener = alb.addListener('Listener', { port: 80, open: false });

    // Default action: 404
    listener.addAction('Default', {
      action: elbv2.ListenerAction.fixedResponse(404, {
        contentType: 'text/plain',
        messageBody: 'Not Found',
      }),
    });

    // Tika target group: /tika*, /detect/*, /meta*
    const tikaTargetGroup = new elbv2.ApplicationTargetGroup(this, 'TikaTargetGroup', {
      vpc, port: 9998, protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [tikaService],
      healthCheck: { path: '/tika', interval: cdk.Duration.seconds(30) },
    });
    listener.addAction('TikaRoute', {
      priority: 10,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/tika*', '/detect/*', '/meta*'])],
      action: elbv2.ListenerAction.forward([tikaTargetGroup]),
    });

    // Siegfried target group: /identify/*
    const siegfriedTargetGroup = new elbv2.ApplicationTargetGroup(this, 'SiegfriedTargetGroup', {
      vpc, port: 5138, protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [siegfriedService],
      healthCheck: {
        protocol: elbv2.Protocol.HTTP,
        path: '/identify/',
        interval: cdk.Duration.seconds(30),
        healthyHttpCodes: '200-405',
      },
    });
    listener.addAction('SiegfriedRoute', {
      priority: 20,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/identify/*'])],
      action: elbv2.ListenerAction.forward([siegfriedTargetGroup]),
    });

    // DROID target group: /api/*
    const droidTargetGroup = new elbv2.ApplicationTargetGroup(this, 'DroidTargetGroup', {
      vpc, port: 8080, protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [droidService],
      healthCheck: { path: '/health', interval: cdk.Duration.seconds(30) },
    });
    listener.addAction('DroidRoute', {
      priority: 30,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/api/*'])],
      action: elbv2.ListenerAction.forward([droidTargetGroup]),
    });

    // MediaInfo target group: /mediainfo/*
    const mediainfoTargetGroup = new elbv2.ApplicationTargetGroup(this, 'MediaInfoTargetGroup', {
      vpc, port: 8081, protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [mediainfoService],
      healthCheck: { path: '/health', interval: cdk.Duration.seconds(30) },
    });
    listener.addAction('MediaInfoRoute', {
      priority: 40,
      conditions: [elbv2.ListenerCondition.pathPatterns(['/mediainfo/*'])],
      action: elbv2.ListenerAction.forward([mediainfoTargetGroup]),
    });

    // --- Lambda Functions ---
    const lambdaLogGroup = new logs.LogGroup(this, 'LambdaLogGroup', {
      retention: logs.RetentionDays.ONE_WEEK,
    });

    const baseLambdaPolicy = new iam.ManagedPolicy(this, 'LambdaBasicPolicy', {
      description: 'Allows Lambda functions to write to CloudWatch Logs',
      statements: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
          resources: [lambdaLogGroup.logGroupArn],
        }),
      ],
    });

    const vpcLambdaRole = new iam.Role(this, 'VpcLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        baseLambdaPolicy,
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
    });

    const nonVpcLambdaRole = new iam.Role(this, 'NonVpcLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [baseLambdaPolicy],
    });

    const backendCode = lambda.Code.fromAsset(path.join(projectRoot, 'backend'));
    const albUrl = `http://${alb.loadBalancerDnsName}`;

    // Shared VPC Lambda props
    const vpcLambdaProps = {
      runtime: lambda.Runtime.PYTHON_3_12,
      code: backendCode,
      timeout: cdk.Duration.seconds(120),
      memorySize: 256,
      role: vpcLambdaRole,
      logGroup: lambdaLogGroup,
      loggingFormat: lambda.LoggingFormat.JSON,
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    };

    // Tika Lambda
    const tikaLambda = new lambda.Function(this, 'TikaLambda', {
      ...vpcLambdaProps,
      handler: 'tika_handler.handler',
      environment: { ALB_URL: albUrl, DOCS_BUCKET: docsBucket.bucketName },
    });

    // Siegfried Lambda
    const siegfriedLambda = new lambda.Function(this, 'SiegfriedLambda', {
      ...vpcLambdaProps,
      handler: 'siegfried_handler.handler',
      environment: { ALB_URL: albUrl, DOCS_BUCKET: docsBucket.bucketName },
    });

    // DROID Lambda
    const droidLambda = new lambda.Function(this, 'DroidLambda', {
      ...vpcLambdaProps,
      handler: 'droid_handler.handler',
      environment: { ALB_URL: albUrl, DOCS_BUCKET: docsBucket.bucketName },
    });

    // MediaInfo Lambda
    const mediainfoLambda = new lambda.Function(this, 'MediaInfoLambda', {
      ...vpcLambdaProps,
      handler: 'mediainfo_handler.handler',
      environment: { ALB_URL: albUrl, DOCS_BUCKET: docsBucket.bucketName },
    });

    // Extract Lambda (no VPC needed — S3 only)
    const extractLambda = new lambda.Function(this, 'ExtractLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      code: backendCode,
      handler: 'extract_handler.handler',
      timeout: cdk.Duration.seconds(300),
      memorySize: 512,
      role: nonVpcLambdaRole,
      logGroup: lambdaLogGroup,
      loggingFormat: lambda.LoggingFormat.JSON,
      environment: { DOCS_BUCKET: docsBucket.bucketName },
    });

    // S3 Report Lambda (no VPC needed — S3 only)
    const reportLambda = new lambda.Function(this, 'ReportLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      code: backendCode,
      handler: 's3_report_handler.handler',
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
      role: nonVpcLambdaRole,
      logGroup: lambdaLogGroup,
      loggingFormat: lambda.LoggingFormat.JSON,
      environment: { DOCS_BUCKET: docsBucket.bucketName },
    });

    // S3 permissions
    docsBucket.grantRead(tikaLambda);
    docsBucket.grantRead(siegfriedLambda);
    docsBucket.grantRead(droidLambda);
    docsBucket.grantRead(mediainfoLambda);
    docsBucket.grantReadWrite(extractLambda);
    docsBucket.grantReadWrite(reportLambda);

    // Allow VPC Lambdas to reach ALB
    const vpcLambdas = [tikaLambda, siegfriedLambda, droidLambda, mediainfoLambda];
    for (const fn of vpcLambdas) {
      alb.connections.allowFrom(fn, ec2.Port.tcp(80));
    }

    // --- AgentCore Gateway ---
    const gateway = new agentcore.Gateway(this, 'Gateway', {
      gatewayName: 'digital-preservation-gw',
      description: 'Gateway exposing digital preservation tools (Tika, Siegfried, DROID, MediaInfo) via MCP',
      authorizerConfiguration: agentcore.GatewayAuthorizer.usingAwsIam(),
      exceptionLevel: agentcore.GatewayExceptionLevel.DEBUG,
    });

    const SDT = agentcore.SchemaDefinitionType;

    // Grant the Gateway's service role permission to invoke all target Lambdas
    // This MUST happen before addLambdaTarget calls — the GatewayTarget custom resource
    // handler validates invoke permissions at creation time.
    const allLambdas = [tikaLambda, siegfriedLambda, droidLambda, mediainfoLambda, extractLambda, reportLambda];
    const invokeGrants = allLambdas.map(fn => fn.grantInvoke(gateway.role));

    // --- Tika tools target ---
    gateway.addLambdaTarget('TikaTarget', {
      gatewayTargetName: 'tika-tools',
      description: 'Apache Tika document processing tools',
      lambdaFunction: tikaLambda,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'tika_process',
          description:
            'Process an S3 file with Apache Tika. Supports text extraction, metadata extraction, and MIME type detection. ' +
            'Tika can handle archives (ZIP, TAR) directly — it recursively parses all contained files.',
          inputSchema: {
            type: SDT.OBJECT,
            properties: {
              s3_key: { type: SDT.STRING, description: 'S3 object key of the file to process' },
              action: { type: SDT.STRING, description: 'Processing action: extract_text, extract_metadata, or detect_type. Defaults to extract_text.' },
            },
            required: ['s3_key'],
          },
        },
      ]),
    });

    // --- Siegfried tools target ---
    gateway.addLambdaTarget('SiegfriedTarget', {
      gatewayTargetName: 'siegfried-tools',
      description: 'Siegfried file format identification tools',
      lambdaFunction: siegfriedLambda,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'siegfried_identify',
          description: 'Identify the file format of an S3 object using Siegfried (PRONOM registry). Returns format name, PUID, MIME type, and match basis.',
          inputSchema: {
            type: SDT.OBJECT,
            properties: {
              s3_key: { type: SDT.STRING, description: 'S3 object key of the file to identify' },
            },
            required: ['s3_key'],
          },
        },
      ]),
    });

    // --- DROID tools target ---
    gateway.addLambdaTarget('DroidTarget', {
      gatewayTargetName: 'droid-tools',
      description: 'DROID file format profiling tools',
      lambdaFunction: droidLambda,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'droid_profile',
          description: 'Profile a file using DROID (Digital Record Object Identification). Returns PRONOM format identification results.',
          inputSchema: {
            type: SDT.OBJECT,
            properties: {
              s3_key: { type: SDT.STRING, description: 'S3 object key of the file to profile' },
            },
            required: ['s3_key'],
          },
        },
      ]),
    });

    // --- MediaInfo tools target ---
    gateway.addLambdaTarget('MediaInfoTarget', {
      gatewayTargetName: 'mediainfo-tools',
      description: 'MediaInfo media file analysis tools',
      lambdaFunction: mediainfoLambda,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'mediainfo_analyze',
          description: 'Analyze a media file (audio, video, image) from S3 using MediaInfo. Returns codec, bitrate, resolution, duration, and other technical metadata.',
          inputSchema: {
            type: SDT.OBJECT,
            properties: {
              s3_key: { type: SDT.STRING, description: 'S3 object key of the media file to analyze' },
            },
            required: ['s3_key'],
          },
        },
      ]),
    });

    // --- Extract archive tools target ---
    gateway.addLambdaTarget('ExtractTarget', {
      gatewayTargetName: 'extract-tools',
      description: 'Archive extraction tools',
      lambdaFunction: extractLambda,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'extract_archive',
          description: 'Extract a ZIP or TAR archive from S3 and write extracted files back to S3. Useful for batch processing archived collections.',
          inputSchema: {
            type: SDT.OBJECT,
            properties: {
              s3_key: { type: SDT.STRING, description: 'S3 object key of the archive file' },
              destination_prefix: { type: SDT.STRING, description: 'S3 key prefix for extracted files. Defaults to <archive_name>_extracted/.' },
            },
            required: ['s3_key'],
          },
        },
      ]),
    });

    // --- S3 report tools target ---
    gateway.addLambdaTarget('ReportTarget', {
      gatewayTargetName: 'report-tools',
      description: 'Analysis report persistence tools',
      lambdaFunction: reportLambda,
      toolSchema: agentcore.ToolSchema.fromInline([
        {
          name: 'save_report_to_s3',
          description: 'Save an analysis report as JSON to S3. Use after running identification/analysis tools to persist results.',
          inputSchema: {
            type: SDT.OBJECT,
            properties: {
              report_data: { type: SDT.STRING, description: 'Report content (JSON string or object) to save' },
              report_name: { type: SDT.STRING, description: 'Report filename (without extension). Defaults to analysis_report_<timestamp>.' },
            },
            required: ['report_data'],
          },
        },
      ]),
    });

    // Add explicit dependencies so each GatewayTarget waits for IAM permissions.
    // The grantInvoke calls attach statements to the gateway role's default policy.
    // We need each GatewayTarget CFN resource to depend on that policy.
    const gatewayRolePolicy = gateway.role.node.tryFindChild('DefaultPolicy');
    const targetIds = ['TikaTarget', 'SiegfriedTarget', 'DroidTarget', 'MediaInfoTarget', 'ExtractTarget', 'ReportTarget'];
    for (const targetId of targetIds) {
      const targetConstruct = gateway.node.tryFindChild(targetId);
      if (targetConstruct && gatewayRolePolicy) {
        targetConstruct.node.addDependency(gatewayRolePolicy);
      }
    }

    // --- AgentCore Runtime ---
    const runtime = new agentcore.Runtime(this, 'AgentRuntime', {
      runtimeName: 'digital_preservation_agent',
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(projectRoot, 'agent'),
      ),
      description: config.agentDescription,
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      environmentVariables: {
        GATEWAY_URL: gateway.gatewayUrl ?? '',
        AWS_REGION: cdk.Stack.of(this).region,
        MODEL_ID: config.agentModelId,
        AGENT_INSTRUCTION: config.agentInstruction,
      },
    });

    gateway.grantInvoke(runtime);
    runtime.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: ['arn:aws:bedrock:*::foundation-model/*'],
      }),
    );
    runtime.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: [`arn:aws:bedrock:*:${cdk.Stack.of(this).account}:inference-profile/*`],
      }),
    );

    // --- Outputs ---
    new cdk.CfnOutput(this, 'RuntimeArn', { value: runtime.agentRuntimeArn });
    new cdk.CfnOutput(this, 'GatewayUrl', { value: gateway.gatewayUrl ?? '' });
    new cdk.CfnOutput(this, 'GatewayId', { value: gateway.gatewayId });
    new cdk.CfnOutput(this, 'AlbDns', { value: alb.loadBalancerDnsName });
    new cdk.CfnOutput(this, 'DocsBucketName', { value: docsBucket.bucketName });

    // --- cdk-nag suppressions ---
    NagSuppressions.addResourceSuppressions(
      vpcLambdaRole,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Wildcard S3 actions from CDK grantRead() scoped to the docs bucket only.',
        },
        {
          id: 'AwsSolutions-IAM4',
          reason: 'AWSLambdaVPCAccessExecutionRole is required for VPC-attached Lambdas.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      nonVpcLambdaRole,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Wildcard S3 actions from CDK grantReadWrite() scoped to the docs bucket only.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      gateway,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Gateway service role needs lambda:InvokeFunction with :* suffix for versioned invocations. ' +
            'Generated by CDK grantInvoke() and scoped to target Lambda functions only.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      runtime,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'AgentCore Runtime execution role requires wildcard permissions for: ' +
            'CloudWatch Logs, workload identity tokens, Bedrock model and inference profile invocation.',
        },
      ],
      true,
    );

    NagSuppressions.addStackSuppressions(this, [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'CDK-managed custom resource, VPC flow log, and AgentCore roles use AWS managed policies by design.',
      },
      {
        id: 'AwsSolutions-IAM5',
        reason: 'CDK-managed custom resource Lambda and AgentCore constructs require broad permissions.',
        appliesTo: ['Resource::*'],
      },
      {
        id: 'AwsSolutions-L1',
        reason: 'CDK-managed custom resource Lambda runtime is controlled by the CDK framework.',
      },
      {
        id: 'AwsSolutions-S1',
        reason: 'The access logs bucket itself does not need server access logs to avoid infinite recursion.',
      },
    ]);
  }
}
