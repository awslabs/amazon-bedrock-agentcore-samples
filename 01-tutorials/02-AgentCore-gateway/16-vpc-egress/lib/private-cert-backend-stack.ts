import * as cdk from 'aws-cdk-lib/core';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as elbv2targets from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

/**
 * Deploys an EC2 instance running a REST API behind an internal ALB
 * with a non-public certificate. Supports two modes:
 *
 * - **Private CA mode**: Pass `certificateAuthorityArn` to issue a certificate
 *   from AWS Private CA (short-lived, 7-day validity).
 * - **Self-signed mode**: Omit `certificateAuthorityArn` to generate a
 *   self-signed certificate via openssl.
 *
 * Both produce a certificate that AgentCore Gateway cannot verify.
 */
export interface PrivateCertBackendStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  baseDomain: string;
  /** If provided, issues a cert from this Private CA. Otherwise generates self-signed. */
  certificateAuthorityArn?: string;
}

export class PrivateCertBackendStack extends cdk.Stack {
  public readonly instance: ec2.Instance;
  public readonly ec2Sg: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: PrivateCertBackendStackProps) {
    super(scope, id, props);

    const privateDomain = `api.internal.${props.baseDomain}`;
    const usePrivateCa = !!props.certificateAuthorityArn;

    // --- Certificate via Lambda Custom Resource ---
    const certHandler = new lambda.Function(this, 'CertHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      timeout: cdk.Duration.minutes(2),
      code: lambda.Code.fromInline(`
import subprocess
import os
import time
import boto3

def handler(event, context):
    request_type = event['RequestType']

    if request_type == 'Delete':
        cert_arn = event.get('PhysicalResourceId', '')
        if cert_arn.startswith('arn:'):
            try:
                boto3.client('acm').delete_certificate(CertificateArn=cert_arn)
            except Exception:
                pass
        return {'PhysicalResourceId': cert_arn}

    domain = event['ResourceProperties']['DomainName']
    ca_arn = event['ResourceProperties'].get('CertificateAuthorityArn', '')

    # Generate private key
    subprocess.run([
        'openssl', 'genrsa', '-out', '/tmp/key.pem', '2048',
    ], check=True, capture_output=True)

    if ca_arn:
        # Private CA mode: generate CSR, issue cert from CA
        subprocess.run([
            'openssl', 'req', '-new', '-key', '/tmp/key.pem',
            '-out', '/tmp/csr.pem', '-subj', f'/CN={domain}',
        ], check=True, capture_output=True)

        with open('/tmp/csr.pem', 'rb') as f:
            csr_bytes = f.read()

        acmpca = boto3.client('acm-pca')
        issue_resp = acmpca.issue_certificate(
            CertificateAuthorityArn=ca_arn,
            Csr=csr_bytes,
            SigningAlgorithm='SHA256WITHRSA',
            Validity={'Value': 7, 'Type': 'DAYS'},
        )

        waiter = acmpca.get_waiter('certificate_issued')
        waiter.wait(
            CertificateAuthorityArn=ca_arn,
            CertificateArn=issue_resp['CertificateArn'],
        )

        get_resp = acmpca.get_certificate(
            CertificateAuthorityArn=ca_arn,
            CertificateArn=issue_resp['CertificateArn'],
        )

        cert_pem = get_resp['Certificate']
        chain_pem = get_resp.get('CertificateChain', '')
    else:
        # Self-signed mode
        subprocess.run([
            'openssl', 'req', '-x509', '-key', '/tmp/key.pem',
            '-out', '/tmp/cert.pem', '-days', '365',
            '-subj', f'/CN={domain}',
        ], check=True, capture_output=True)

        with open('/tmp/cert.pem') as f:
            cert_pem = f.read()
        chain_pem = ''

    with open('/tmp/key.pem') as f:
        key_pem = f.read()

    for p in ['/tmp/key.pem', '/tmp/cert.pem', '/tmp/csr.pem']:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass

    acm_client = boto3.client('acm')

    if request_type == 'Update':
        old_arn = event.get('PhysicalResourceId', '')
        if old_arn.startswith('arn:'):
            try:
                acm_client.delete_certificate(CertificateArn=old_arn)
            except Exception:
                pass

    import_args = {
        'Certificate': cert_pem.encode() if isinstance(cert_pem, str) else cert_pem,
        'PrivateKey': key_pem.encode(),
    }
    if chain_pem:
        import_args['CertificateChain'] = chain_pem.encode() if isinstance(chain_pem, str) else chain_pem

    resp = acm_client.import_certificate(**import_args)

    return {
        'PhysicalResourceId': resp['CertificateArn'],
        'Data': {'CertificateArn': resp['CertificateArn']},
    }
`),
    });

    const policyActions = ['acm:ImportCertificate', 'acm:DeleteCertificate'];
    if (usePrivateCa) {
      policyActions.push('acm-pca:IssueCertificate', 'acm-pca:GetCertificate');
    }

    certHandler.addToRolePolicy(new iam.PolicyStatement({
      actions: policyActions,
      resources: ['*'],
    }));

    const certProvider = new cr.Provider(this, 'CertProvider', {
      onEventHandler: certHandler,
    });

    const certProperties: Record<string, string> = { DomainName: privateDomain };
    if (props.certificateAuthorityArn) {
      certProperties['CertificateAuthorityArn'] = props.certificateAuthorityArn;
    }

    const cert = new cdk.CustomResource(this, 'Cert', {
      serviceToken: certProvider.serviceToken,
      properties: certProperties,
    });

    const certArn = cert.getAttString('CertificateArn');
    const certificate = acm.Certificate.fromCertificateArn(this, 'ImportedCert', certArn);

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

    // --- Internal ALB with non-public certificate ---
    const albSg = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc: props.vpc,
      description: `Internal ALB with ${usePrivateCa ? 'private CA' : 'self-signed'} cert`,
      allowAllOutbound: true,
    });
    albSg.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
    albSg.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      'Allow HTTPS from VPC',
    );

    this.ec2Sg.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(8000),
      'Allow HTTP from VPC (backend ALB and proxy ALB)',
    );

    const accessLogBucket = new s3.Bucket(this, 'AlbAccessLogs', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [{ expiration: cdk.Duration.days(30) }],
    });

    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      vpc: props.vpc,
      internetFacing: false,
      securityGroup: albSg,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    alb.logAccessLogs(accessLogBucket, 'alb-logs');

    const httpsListener = alb.addListener('HttpsListener', {
      port: 443,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      certificates: [certificate],
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

    // --- Outputs ---
    const certType = usePrivateCa ? 'private CA' : 'self-signed';

    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: alb.loadBalancerDnsName,
      description: `Internal ALB DNS (${certType} cert — not usable with AgentCore directly)`,
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

    new cdk.CfnOutput(this, 'CertArn', {
      value: certArn,
      description: `Certificate ARN (${certType} — not trusted by AgentCore)`,
    });

    new cdk.CfnOutput(this, 'ApiKey', {
      value: 'vpc-egress-lab-api-key',
      description: 'API key for the simple REST API (x-api-key header)',
    });

    new cdk.CfnOutput(this, 'CertDomain', {
      value: privateDomain,
      description: `Domain on the ${certType} certificate`,
    });

    NagSuppressions.addStackSuppressions(this, [
      { id: 'AwsSolutions-IAM4', reason: 'SSM managed policy and Lambda basic execution role use AWS managed policies' },
      { id: 'AwsSolutions-IAM5', reason: 'SSM, ACM, and ACM-PCA operations require wildcards' },
      { id: 'AwsSolutions-EC26', reason: 'EBS encryption not needed for lab instance' },
      { id: 'AwsSolutions-EC28', reason: 'Detailed monitoring not needed for lab instance' },
      { id: 'AwsSolutions-EC29', reason: 'Lab instance does not need termination protection' },
      { id: 'AwsSolutions-S1', reason: 'Access log bucket does not need its own access logs' },
      { id: 'AwsSolutions-EC23', reason: 'ALB is internal, SG allows VPC CIDR only' },
      { id: 'AwsSolutions-L1', reason: 'Lambda runtime is current at time of writing' },
      { id: 'CdkNagValidationFailure', reason: 'Security group uses VPC CIDR intrinsic reference' },
    ]);
  }
}
