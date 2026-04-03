import * as cdk from 'aws-cdk-lib/core';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as elbv2targets from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as route53targets from 'aws-cdk-lib/aws-route53-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

/**
 * Deploys an EC2 instance running a REST API behind an internal ALB
 * with a public certificate, and a Route 53 private hosted zone
 * that resolves to the ALB within the VPC.
 *
 * This represents a setup where the domain is only resolvable inside
 * the VPC (private hosted zone), but the TLS certificate is publicly
 * trusted. VPC Lattice requires a publicly resolvable domain — the
 * routingDomain (ALB DNS) provides this.
 */
export interface PrivateDomainStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  baseDomain: string;
  publicCertArn: string;
}

export class PrivateDomainStack extends cdk.Stack {
  public readonly instance: ec2.Instance;
  public readonly ec2Sg: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: PrivateDomainStackProps) {
    super(scope, id, props);

    const publicCert = acm.Certificate.fromCertificateArn(this, 'PublicCert', props.publicCertArn);

    // --- EC2 Instance running simple REST API on HTTP :8000 ---
    this.ec2Sg = new ec2.SecurityGroup(this, 'Ec2Sg', {
      vpc: props.vpc,
      description: 'Simple API EC2 instance',
      allowAllOutbound: true,
    });
    this.ec2Sg.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);

    this.instance = new ec2.Instance(this, 'SimpleApiInstance', {
      vpc: props.vpc,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroup: this.ec2Sg,
      ssmSessionPermissions: true,
    });

    this.instance.addUserData(
      '#!/bin/bash',
      'dnf update -y',
      'dnf install -y python3-pip',
      'pip3 install fastapi uvicorn',
      'mkdir -p /opt/simple-api',
      "cat > /opt/simple-api/app.py << 'PYEOF'",
      'from fastapi import FastAPI, Depends, Header, HTTPException',
      '',
      'API_KEY = "vpc-egress-lab-api-key"',
      '',
      '',
      'def verify_api_key(x_api_key: str = Header(...)):',
      '    if x_api_key != API_KEY:',
      '        raise HTTPException(status_code=403, detail="Invalid API key")',
      '',
      '',
      'app = FastAPI(dependencies=[Depends(verify_api_key)])',
      'items: list[dict] = []',
      '',
      '',
      '@app.get("/health")',
      'def health():',
      '    return {"status": "ok"}',
      '',
      '',
      '@app.get("/items")',
      'def list_items():',
      '    return items',
      '',
      '',
      '@app.post("/items")',
      'def create_item(item: dict):',
      '    items.append(item)',
      '    return item',
      'PYEOF',
      "cat > /etc/systemd/system/simple-api.service << 'SVCEOF'",
      '[Unit]',
      'Description=Simple API Server',
      'After=network.target',
      '',
      '[Service]',
      'Type=simple',
      'WorkingDirectory=/opt/simple-api',
      'ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000',
      'Restart=always',
      '',
      '[Install]',
      'WantedBy=multi-user.target',
      'SVCEOF',
      'systemctl daemon-reload',
      'systemctl enable simple-api',
      'systemctl start simple-api',
    );

    // --- Internal ALB with public certificate ---
    const albSg = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc: props.vpc,
      description: 'Internal ALB with public cert - HTTPS from VPC',
      allowAllOutbound: true,
    });
    albSg.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
    albSg.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      'Allow HTTPS from VPC',
    );

    this.ec2Sg.addIngressRule(
      albSg,
      ec2.Port.tcp(8000),
      'Allow traffic from ALB',
    );

    const accessLogBucket = new s3.Bucket(this, 'AlbAccessLogs', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [{ expiration: cdk.Duration.days(30) }],
    });

    const alb = new elbv2.ApplicationLoadBalancer(this, 'InternalAlb', {
      vpc: props.vpc,
      internetFacing: false,
      securityGroup: albSg,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    alb.logAccessLogs(accessLogBucket, 'alb-logs');

    const httpsListener = alb.addListener('HttpsListener', {
      port: 443,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      certificates: [publicCert],
    });

    httpsListener.addTargets('Ec2Target', {
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new elbv2targets.InstanceTarget(this.instance, 8000)],
      healthCheck: {
        path: '/health',
        port: '8000',
        healthyHttpCodes: '200',
      },
    });

    // --- Route 53 Private Hosted Zone ---
    // This domain only resolves inside the VPC. VPC Lattice cannot use it
    // for its resource configuration — that's what routingDomain solves.
    const privateZone = new route53.PrivateHostedZone(this, 'PrivateZone', {
      zoneName: `internal.${props.baseDomain}`,
      vpc: props.vpc,
    });

    new route53.ARecord(this, 'AlbAliasRecord', {
      zone: privateZone,
      recordName: 'api',
      target: route53.RecordTarget.fromAlias(
        new route53targets.LoadBalancerTarget(alb),
      ),
    });

    // Also add a direct EC2 record for the "no ALB" scenario explanation
    new route53.ARecord(this, 'Ec2DirectRecord', {
      zone: privateZone,
      recordName: 'direct',
      target: route53.RecordTarget.fromIpAddresses(this.instance.instancePrivateIp),
    });

    // --- Outputs ---
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: alb.loadBalancerDnsName,
      description: 'Internal ALB DNS (publicly resolvable — use as routingDomain)',
    });

    new cdk.CfnOutput(this, 'AlbSgId', {
      value: albSg.securityGroupId,
    });

    new cdk.CfnOutput(this, 'Ec2InstanceId', {
      value: this.instance.instanceId,
      description: 'SSM Session Manager: aws ssm start-session --target <id>',
    });

    new cdk.CfnOutput(this, 'Ec2PrivateIp', {
      value: this.instance.instancePrivateIp,
    });

    new cdk.CfnOutput(this, 'PrivateDomainAlb', {
      value: `api.internal.${props.baseDomain}`,
      description: 'Private domain pointing to ALB (only resolvable inside VPC)',
    });

    new cdk.CfnOutput(this, 'ApiKey', {
      value: 'vpc-egress-lab-api-key',
      description: 'API key for the simple REST API (x-api-key header)',
    });

    new cdk.CfnOutput(this, 'PrivateDomainDirect', {
      value: `direct.internal.${props.baseDomain}`,
      description: 'Private domain pointing to EC2 IP directly (only resolvable inside VPC)',
    });

    NagSuppressions.addStackSuppressions(this, [
      { id: 'AwsSolutions-IAM4', reason: 'SSM managed policy required for Session Manager access' },
      { id: 'AwsSolutions-IAM5', reason: 'SSM managed policies use wildcards' },
      { id: 'AwsSolutions-EC26', reason: 'EBS encryption not needed for lab instance' },
      { id: 'AwsSolutions-EC28', reason: 'Detailed monitoring not needed for lab instance' },
      { id: 'AwsSolutions-EC29', reason: 'Lab instance does not need termination protection' },
      { id: 'AwsSolutions-S1', reason: 'Access log bucket does not need its own access logs' },
      { id: 'AwsSolutions-EC23', reason: 'ALB is internal, SG allows VPC CIDR only' },
      { id: 'CdkNagValidationFailure', reason: 'Security group uses VPC CIDR intrinsic reference' },
    ]);
  }
}
